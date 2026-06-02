/**
 * CodeRunnerPanel — editor + interactive terminal wired to the WebSocket runner.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Play,
  Square,
  Terminal as TerminalIcon,
  FileCode2,
  Scroll,
  Lightbulb,
  Bot,
  GripHorizontal,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { Profile, getRunnerWsUrl } from "../lib/api";
import { getTokens } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import Terminal from "./Terminal";
import AIMentorChat from "./AIMentorChat";

const SYM_OK = "\x1b[32m✔\x1b[0m";
const SYM_FAIL = "\x1b[31m✘\x1b[0m";
const ANSI_CYAN = "\x1b[36m";
const ANSI_DIM = "\x1b[90m";
const ANSI_RED = "\x1b[31m";
const ANSI_YELLOW = "\x1b[33m";
const ANSI_RESET = "\x1b[0m";

const normaliseEol = (s) => (s ?? "").replace(/\r?\n/g, "\r\n");

// Перенос строк по словам — xterm не делает word-wrap для длинных строк.
// Возвращает массив строк не длиннее `width` символов.
const wrapWords = (text, width = 70) => {
  const result = [];
  for (const paragraph of text.split(/\r?\n/)) {
    if (!paragraph) { result.push(""); continue; }
    const words = paragraph.split(/\s+/);
    let line = "";
    for (const w of words) {
      if (!line) { line = w; continue; }
      if ((line + " " + w).length > width) {
        result.push(line);
        line = w;
      } else {
        line += " " + w;
      }
    }
    if (line) result.push(line);
  }
  return result;
};

const MIN_TERMINAL_H = 200;
const MAX_TERMINAL_H = 1000;
const DEFAULT_TERMINAL_H = 550;

export default function CodeRunnerPanel({
  task,
  code,
  onChange,
  onTestPassed,
  inventoryCounts = { ai_summons: 0, hint_scrolls: 0, skeleton_scrolls: 0 },
  onInventoryUpdate,
}) {
  const { t } = useI18n();
  const termRef = useRef(null);
  const wsRef = useRef(null);
  const [running, setRunning] = useState(false);
  const [lastExit, setLastExit] = useState(null);
  const [usingItem, setUsingItem] = useState(false);
  const [termH, setTermH] = useState(DEFAULT_TERMINAL_H);
  const [mentorOpen, setMentorOpen] = useState(false);
  const dragRef = useRef(null);

  // Снимок оригинального starter-кода задачи — обновляется ТОЛЬКО при смене
  // task.id. Reset-кнопка ниже всегда восстанавливает код из этого снимка
  // и не тратит инвентарь (в отличие от Skeleton Scroll, который добавляет
  // boilerplate сверх текущего кода и расходует item).
  const initialCodeRef = useRef("");
  useEffect(() => {
    if (!task?.id) return;
    initialCodeRef.current = task?.data?.starter || "";
  }, [task?.id]);

  const handleResetCode = useCallback(() => {
    onChange(initialCodeRef.current || "");
    toast(
      initialCodeRef.current
        ? t("codeRunner.resetReverted")
        : t("codeRunner.resetCleared"),
      { duration: 2000 }
    );
  }, [onChange, t]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        try { wsRef.current.close(); } catch { /* noop */ }
        wsRef.current = null;
      }
    };
  }, []);

  // ── Drag-to-resize terminal ───────────────────────────────────────────────
  const onDragStart = (e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = termH;

    const onMove = (ev) => {
      const delta = startY - ev.clientY;
      setTermH(Math.min(MAX_TERMINAL_H, Math.max(MIN_TERMINAL_H, startH + delta)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const stopRun = useCallback(() => {
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* noop */ }
      wsRef.current = null;
    }
    setRunning(false);
  }, []);

  const runCode = useCallback(() => {
    if (running) return;

    const { access } = getTokens();
    if (!access) {
      toast.error(t("codeRunner.authRequired"));
      return;
    }

    const wsUrl = getRunnerWsUrl(access);
    if (!wsUrl) {
      toast.error(t("codeRunner.noRunnerUrl"));
      return;
    }

    const term = termRef.current;
    term?.clear();
    term?.write(
      `${ANSI_CYAN}user@academy:~$${ANSI_RESET} python main.py\r\n${ANSI_DIM}─────────────────────────────────────────${ANSI_RESET}\r\n`
    );

    setRunning(true);
    setLastExit(null);

    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      term?.write(`${ANSI_RED}[connect failed] ${err?.message || err}${ANSI_RESET}\r\n`);
      setRunning(false);
      return;
    }
    wsRef.current = ws;
    let testPassedFired = false;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "run", code: code || "", language: "python" }));
    };

    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      switch (msg.type) {
        case "stdout":
          term?.write(normaliseEol(msg.data));
          break;
        case "stderr":
          term?.write(`${ANSI_RED}${normaliseEol(msg.data)}${ANSI_RESET}`);
          break;
        case "error":
          term?.write(`\r\n${ANSI_YELLOW}[!] ${msg.message}${ANSI_RESET}\r\n`);
          break;
        case "exit": {
          const sym = msg.code === 0 ? SYM_OK : SYM_FAIL;
          term?.write(
            `\r\n${ANSI_DIM}─────────────────────────────────────────${ANSI_RESET}\r\n` +
              `${sym} exit ${msg.code} · ${Number(msg.duration || 0).toFixed(2)}s\r\n`
          );
          setLastExit({ code: msg.code, duration: msg.duration });
          if (msg.code === 0 && !testPassedFired && onTestPassed) {
            testPassedFired = true;
            onTestPassed({ status: "success", code, exit_code: msg.code, duration: msg.duration });
          }
          try { ws.close(); } catch { /* noop */ }
          break;
        }
        default:
          term?.write(`${ANSI_DIM}[unknown event ${JSON.stringify(msg)}]${ANSI_RESET}\r\n`);
      }
    };

    ws.onerror = () => { term?.write(`\r\n${ANSI_RED}[ws error]${ANSI_RESET}\r\n`); };

    ws.onclose = (ev) => {
      wsRef.current = null;
      setRunning(false);
      if (ev.code === 4401) {
        term?.write(`\r\n${ANSI_RED}[auth required — refresh login]${ANSI_RESET}\r\n`);
        toast.error(t("codeRunner.sessionExpired"));
      }
    };
  }, [running, code, onTestPassed, t]);

  // ── Inventory handlers ────────────────────────────────────────────────────
  const handleUseItem = useCallback(
    async (itemType, itemName) => {
      if (usingItem) return false;
      setUsingItem(true);
      try {
        const res = await Profile.consumeItem(itemType);
        toast.success(
          t("codeRunner.itemUsed")
            .replace("{item}", itemName)
            .replace("{count}", res.remaining)
        );
        if (onInventoryUpdate) onInventoryUpdate(itemType, res.remaining);
        return true;
      } catch (error) {
        toast.error(
          error.response?.data?.detail || t("codeRunner.itemFail")
        );
        return false;
      } finally {
        setUsingItem(false);
      }
    },
    [usingItem, onInventoryUpdate, t]
  );

  const handleSkeletonScroll = async () => {
    const ok = await handleUseItem("skeleton_scrolls", t("codeRunner.items.architect"));
    if (ok) {
      const boilerplate =
        task?.data?.starter ||
        `${t("codeRunner.starterComment")}\ndef main():\n    pass\n\nif __name__ == '__main__':\n    main()\n`;
      onChange(code ? `${code}\n\n${boilerplate}` : boilerplate);
    }
  };

  const handleHintScroll = async () => {
    const ok = await handleUseItem("hint_scrolls", t("codeRunner.items.clarity"));
    if (!ok) return;

    const hint =
      task?.data?.hint ||
      t("codeRunner.hintFallback");

    // Подсказку выводим прямо в терминал редактора — он всегда
    // привязан к панели и виден на любой ширине экрана (на 32:9
    // top-right toast визуально «уходит за экран»). Если терминал
    // ещё не смонтирован — фоллбэк на тост.
    if (termRef.current?.writeln) {
      termRef.current.writeln(`\r\n${ANSI_YELLOW}${t("codeRunner.clarityHeader")}${ANSI_RESET}`);
      wrapWords(hint, 70).forEach((line) => {
        termRef.current.writeln(`${ANSI_YELLOW}│${ANSI_RESET} ${line}`);
      });
      termRef.current.writeln(`${ANSI_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━${ANSI_RESET}\r\n`);
    } else {
      toast(`💡 ${hint}`, { duration: 6000 });
    }
  };

  const lines = code ? code.split("\n").length : 1;
  const lineArray = Array.from({ length: Math.max(25, lines) }, (_, i) => i + 1);

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] font-mono">
      {/* Editor Tabs & Toolbar */}
      <div className="flex items-center bg-[#252526] overflow-x-auto select-none border-l border-[#333]">
        <div className="flex items-center gap-2 bg-[#1e1e1e] px-4 py-2 border-t border-[#3794ff] min-w-max cursor-pointer">
          <FileCode2 size={14} className="text-[#519aba]" />
          <span className="text-xs text-white">main.py</span>
        </div>

        {/* Inventory toolbar */}
        <div className="flex items-center gap-3 px-4 py-1 border-l border-[#333] ml-2">
          <button
            onClick={handleSkeletonScroll}
            disabled={usingItem || !inventoryCounts?.skeleton_scrolls}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.skeleton_scrolls > 0 ? "text-[#e5c07b] hover:bg-[#333] cursor-pointer" : "text-gray-600 cursor-not-allowed"}`}
            title={t("codeRunner.items.architect")}
          >
            <Scroll size={14} />
            <span>{inventoryCounts?.skeleton_scrolls || 0}</span>
          </button>

          <button
            onClick={handleHintScroll}
            disabled={usingItem || !inventoryCounts?.hint_scrolls}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.hint_scrolls > 0 ? "text-[#98c379] hover:bg-[#333] cursor-pointer" : "text-gray-600 cursor-not-allowed"}`}
            title={t("codeRunner.items.clarity")}
          >
            <Lightbulb size={14} />
            <span>{inventoryCounts?.hint_scrolls || 0}</span>
          </button>

          <button
            onClick={() => setMentorOpen(true)}
            className="flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors text-[#c678dd] hover:bg-[#333] cursor-pointer"
            title={t("codeRunner.mentor.open")}
          >
            <Bot size={14} />
            <span>{inventoryCounts?.ai_summons || 0}</span>
          </button>
        </div>

        <div className="flex-1" />
        <div className="px-3 flex items-center gap-2 bg-[#252526]">
          {/* Reset code — всегда активна, не тратит инвентарь.
              Возвращает к initialCodeRef (стартеру задачи). */}
          <button
            onClick={handleResetCode}
            title={t("codeRunner.resetTitle")}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-[#3c3c3c] hover:bg-[#4a4a4a] text-[#cccccc] hover:text-white text-xs transition-colors"
          >
            <RotateCcw size={11} />
            Reset
          </button>

          {running ? (
            <button
              onClick={stopRun}
              className="flex items-center gap-1.5 px-3 py-1 rounded bg-[#a31515] hover:bg-[#c41a1a] text-white text-xs transition-colors"
            >
              <Square size={11} fill="currentColor" />
              Stop
            </button>
          ) : (
            <button
              onClick={runCode}
              className="flex items-center gap-1.5 px-3 py-1 rounded bg-[#0e639c] hover:bg-[#1177bb] text-white text-xs transition-colors"
            >
              <Play size={12} fill="currentColor" />
              Run Code
            </button>
          )}
        </div>
      </div>

      {/* Breadcrumbs */}
      <div className="flex items-center gap-1.5 px-4 py-1.5 text-[11px] text-[#cccccc] bg-[#1e1e1e] border-b border-[#333] border-l select-none shadow-sm z-10">
        <span className="hover:text-white cursor-pointer">rpg-academy</span>
        <span className="opacity-50">&gt;</span>
        <span className="hover:text-white cursor-pointer">mission-{task?.mission || "X"}</span>
        <span className="opacity-50">&gt;</span>
        <span className="hover:text-white cursor-pointer">main.py</span>
      </div>

      {/* Editor */}
      <div className="flex-1 relative bg-[#1e1e1e] flex border-l border-[#333] min-h-0">
        <div className="w-12 bg-[#1e1e1e] border-r border-[#333] flex flex-col items-end py-4 pr-3 text-[#858585] text-xs select-none overflow-hidden font-mono">
          {lineArray.map((n) => (
            <span key={n} className="leading-6 opacity-50">{n}</span>
          ))}
        </div>
        <textarea
          value={code || ""}
          onChange={(e) => onChange(e.target.value)}
          spellCheck="false"
          className="w-full h-full p-4 bg-transparent text-[13px] font-mono text-[#d4d4d4] resize-none focus:outline-none focus:ring-0 leading-6"
          placeholder={t("codeRunner.placeholder")}
        />
      </div>

      {/* Drag handle */}
      <div
        ref={dragRef}
        onMouseDown={onDragStart}
        className="h-2 bg-[#252526] border-t border-b border-[#333] flex items-center justify-center cursor-row-resize hover:bg-[#2a2d2e] select-none group"
        title={t("codeRunner.resizeTitle")}
      >
        <GripHorizontal size={12} className="text-[#555] group-hover:text-[#888]" />
      </div>

      {/* Terminal — adaptive height */}
      <div style={{ height: termH }} className="flex flex-col bg-[#1e1e1e] border-l border-[#333] flex-shrink-0">
        <div className="flex items-center gap-4 px-4 pt-2 border-b border-[#333] select-none">
          <span className="text-[11px] uppercase tracking-wider text-white border-b border-white pb-2 font-semibold flex items-center gap-2">
            <TerminalIcon size={14} /> TERMINAL
          </span>
          {running && (
            <span className="text-[11px] tracking-wider text-[#cca700] pb-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#cca700] animate-pulse" />
              running…
            </span>
          )}
          {!running && lastExit && (
            <span className={`text-[11px] tracking-wider pb-2 ${lastExit.code === 0 ? "text-[#23d18b]" : "text-[#f14c4c]"}`}>
              exit {lastExit.code} · {Number(lastExit.duration || 0).toFixed(2)}s
            </span>
          )}
        </div>
        <div className="flex-1 min-h-0 p-2">
          <Terminal ref={termRef} />
        </div>
      </div>

      {/* AI-наставник (Sage) — контекстный чат, выезжает справа */}
      <AIMentorChat
        open={mentorOpen}
        onClose={() => setMentorOpen(false)}
        task={task}
        code={code}
        summons={inventoryCounts?.ai_summons || 0}
        onInventoryUpdate={onInventoryUpdate}
      />
    </div>
  );
}
