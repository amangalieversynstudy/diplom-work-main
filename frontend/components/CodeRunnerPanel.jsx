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
} from "lucide-react";
import { toast } from "sonner";
import { AIAssist, Profile, getRunnerWsUrl } from "../lib/api";
import { getTokens } from "../lib/auth";
import Terminal from "./Terminal";

const SYM_OK = "\x1b[32m✔\x1b[0m";
const SYM_FAIL = "\x1b[31m✘\x1b[0m";
const ANSI_CYAN = "\x1b[36m";
const ANSI_DIM = "\x1b[90m";
const ANSI_RED = "\x1b[31m";
const ANSI_YELLOW = "\x1b[33m";
const ANSI_RESET = "\x1b[0m";

const normaliseEol = (s) => (s ?? "").replace(/\r?\n/g, "\r\n");

const MIN_TERMINAL_H = 120;
const MAX_TERMINAL_H = 600;

export default function CodeRunnerPanel({
  task,
  code,
  onChange,
  onTestPassed,
  inventoryCounts = { ai_summons: 0, hint_scrolls: 0, skeleton_scrolls: 0 },
  onInventoryUpdate,
}) {
  const termRef = useRef(null);
  const wsRef = useRef(null);
  const [running, setRunning] = useState(false);
  const [lastExit, setLastExit] = useState(null);
  const [usingItem, setUsingItem] = useState(false);
  const [termH, setTermH] = useState(280);
  const dragRef = useRef(null);

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
      toast.error("Войдите в систему, чтобы запустить код.");
      return;
    }

    const wsUrl = getRunnerWsUrl(access);
    if (!wsUrl) {
      toast.error("Не удалось вычислить адрес раннера.");
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
        toast.error("Сессия истекла. Войдите снова.");
      }
    };
  }, [running, code, onTestPassed]);

  // ── Inventory handlers ────────────────────────────────────────────────────
  const handleUseItem = useCallback(
    async (itemType, itemName) => {
      if (usingItem) return false;
      setUsingItem(true);
      try {
        const res = await Profile.consumeItem(itemType);
        toast.success(`${itemName} использован! Осталось: ${res.remaining}`);
        if (onInventoryUpdate) onInventoryUpdate(itemType, res.remaining);
        return true;
      } catch (error) {
        toast.error(
          error.response?.data?.detail || "Не удалось использовать предмет или он закончился."
        );
        return false;
      } finally {
        setUsingItem(false);
      }
    },
    [usingItem, onInventoryUpdate]
  );

  const handleSkeletonScroll = async () => {
    const ok = await handleUseItem("skeleton_scrolls", "Свиток Архитектора");
    if (ok) {
      const boilerplate =
        task?.data?.starter ||
        "# Напишите свой код ниже\ndef main():\n    pass\n\nif __name__ == '__main__':\n    main()\n";
      onChange(code ? `${code}\n\n${boilerplate}` : boilerplate);
    }
  };

  const handleHintScroll = async () => {
    const ok = await handleUseItem("hint_scrolls", "Зелье Ясности");
    if (ok) {
      const hint =
        task?.data?.hint ||
        "Проверьте правильность отступов и синтаксис объявления функций.";
      toast(`💡 Подсказка: ${hint}`, { duration: 6000 });
    }
  };

  const handleAISummon = async () => {
    if (usingItem) return;
    if (!inventoryCounts?.ai_summons) {
      toast.error("Нет вызовов AI-помощника.");
      return;
    }

    setUsingItem(true);
    termRef.current?.writeln(`\r\n${ANSI_CYAN}🔮 Вызываю Мудреца...${ANSI_RESET}`);

    try {
      const taskDesc =
        task?.body_ru || task?.body_en || task?.data?.hint || task?.title_ru || "";
      // Backend handles decrement internally — do NOT call consumeItem separately
      const { hint, remaining_summons } = await AIAssist.getHint(
        code || "",
        taskDesc,
        task?.data?.language || "python"
      );
      if (onInventoryUpdate && remaining_summons !== undefined) {
        onInventoryUpdate("ai_summons", remaining_summons);
      }
      termRef.current?.writeln(`\r\n\x1b[35m╔══ 🤖 Мудрец говорит ══╗\x1b[0m`);
      hint.split("\n").forEach((line) => {
        termRef.current?.writeln(`\x1b[35m║\x1b[0m ${line}`);
      });
      termRef.current?.writeln(`\x1b[35m╚══════════════════════╝\x1b[0m\r\n`);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      termRef.current?.writeln(
        `\r\n${ANSI_RED}⚠ ${detail || "Мудрец недоступен. Попробуй ещё раз."}${ANSI_RESET}\r\n`
      );
      if (detail) toast.error(detail);
    } finally {
      setUsingItem(false);
    }
  };

  const lines = code ? code.split("\n").length : 1;
  const lineArray = Array.from({ length: Math.max(25, lines) }, (_, i) => i + 1);

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] font-mono overflow-hidden">
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
            title="Свиток Архитектора"
          >
            <Scroll size={14} />
            <span>{inventoryCounts?.skeleton_scrolls || 0}</span>
          </button>

          <button
            onClick={handleHintScroll}
            disabled={usingItem || !inventoryCounts?.hint_scrolls}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.hint_scrolls > 0 ? "text-[#98c379] hover:bg-[#333] cursor-pointer" : "text-gray-600 cursor-not-allowed"}`}
            title="Зелье Ясности"
          >
            <Lightbulb size={14} />
            <span>{inventoryCounts?.hint_scrolls || 0}</span>
          </button>

          <button
            onClick={handleAISummon}
            disabled={usingItem || !inventoryCounts?.ai_summons}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.ai_summons > 0 ? "text-[#c678dd] hover:bg-[#333] cursor-pointer" : "text-gray-600 cursor-not-allowed"}`}
            title="Вызвать AI-помощника"
          >
            <Bot size={14} />
            <span>{inventoryCounts?.ai_summons || 0}</span>
          </button>
        </div>

        <div className="flex-1" />
        <div className="px-3 flex items-center gap-2 bg-[#252526]">
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
          placeholder="# Напиши свой код здесь..."
        />
      </div>

      {/* Drag handle */}
      <div
        ref={dragRef}
        onMouseDown={onDragStart}
        className="h-2 bg-[#252526] border-t border-b border-[#333] flex items-center justify-center cursor-row-resize hover:bg-[#2a2d2e] select-none group"
        title="Потяни чтобы изменить размер терминала"
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
    </div>
  );
}
