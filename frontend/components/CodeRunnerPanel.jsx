/**
 * CodeRunnerPanel — editor + interactive terminal wired to the WebSocket runner.
 */

import { forwardRef, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
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
  Maximize2,
  Minimize2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { toast } from "sonner";
import { Profile, getRunnerWsUrl } from "../lib/api";
import { getTokens } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { indentAction, newlineAction } from "../lib/editorKeys";
import { createTracker } from "../lib/provenance";
import { isAccidentalStop } from "../lib/runGuard";
import { detectErrorType } from "../lib/errorHelp";
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

const MIN_TERMINAL_H = 160;
const MAX_TERMINAL_H = 1000;
const DEFAULT_TERMINAL_H = 260;

function CodeRunnerPanel(
  {
    task,
    code,
    onChange,
    onTaskResult,
    onRunStateChange,
    inventoryCounts = { ai_summons: 0, hint_scrolls: 0, skeleton_scrolls: 0 },
    onInventoryUpdate,
    pulseHelp = false, // после нескольких неудач подсвечиваем зелье и Мудреца
  },
  ref
) {
  const { t } = useI18n();
  const termRef = useRef(null);
  const wsRef = useRef(null);
  // синхронная защита от двойного щелчка: state `running` обновляется только после рендера
  const runLockRef = useRef(false);
  const runStartedAtRef = useRef(0);
  const userStoppedRef = useRef(false);
  const [running, setRunning] = useState(false);
  const [lastExit, setLastExit] = useState(null);
  const [usingItem, setUsingItem] = useState(false);
  // подсказки, открытые на этом шаге: остаются на экране между запусками
  const [openedHints, setOpenedHints] = useState([]);
  useEffect(() => {
    setOpenedHints([]);
  }, [task?.id]);
  const [termH, setTermH] = useState(DEFAULT_TERMINAL_H);
  const [mentorOpen, setMentorOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [termCollapsed, setTermCollapsed] = useState(false);
  const dragRef = useRef(null);

  useEffect(() => {
    if (window.innerWidth < 640) setTermH(180);
  }, []);

  // Снимок оригинального starter-кода задачи — обновляется ТОЛЬКО при смене
  // task.id. Reset-кнопка ниже всегда восстанавливает код из этого снимка
  // и не тратит инвентарь (в отличие от Skeleton Scroll, который добавляет
  // boilerplate сверх текущего кода и расходует item).
  const initialCodeRef = useRef("");
  // Сколько символов набрано и сколько вставлено (только числа, см. lib/provenance.js): уходит
  // на сервер вместе с запуском, чтобы преподаватель видел, как появилось решение.
  const trackerRef = useRef(null);
  if (!trackerRef.current) trackerRef.current = createTracker();
  useEffect(() => {
    if (!task?.id) return;
    initialCodeRef.current = task?.data?.starter || "";
    trackerRef.current.reset();
    // снимок заготовки и счётчики только при смене шага, а не при каждой правке данных задачи
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.id]);

  const handleResetCode = useCallback(() => {
    trackerRef.current.reset(); // код начат заново, и счёт тоже
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

  // Esc выходит из полноэкранного режима редактора.
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

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
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  };

  const stopRun = useCallback(() => {
    // Двойной щелчок по «Запустить»: второй клик попадает на «Стоп» и отменял бы запуск.
    if (isAccidentalStop(runStartedAtRef.current, Date.now())) return;
    userStoppedRef.current = true;
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* noop */ }
      wsRef.current = null;
    }
    runLockRef.current = false;
    setRunning(false);
  }, []);

  const runCode = useCallback(() => {
    if (running || runLockRef.current) return;

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

    runLockRef.current = true;
    runStartedAtRef.current = Date.now();
    userStoppedRef.current = false;
    setRunning(true);
    setLastExit(null);
    onRunStateChange?.("running");

    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      term?.write(`${ANSI_RED}[connect failed] ${err?.message || err}${ANSI_RESET}\r\n`);
      runLockRef.current = false;
      setRunning(false);
      return;
    }
    wsRef.current = ws;
    // The server grades the run (it alone knows the expected output) and sends
    // a "result" event just before "exit". Runs without a task id are free
    // practice: only the exit code matters.
    let verdict = null;
    let exited = false;
    let stderrText = "";

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "run",
          code: code || "",
          language: "python",
          ...(task?.id ? { task_id: task.id, provenance: trackerRef.current.snapshot() } : {}),
        })
      );
    };

    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      switch (msg.type) {
        case "stdout":
          term?.write(normaliseEol(msg.data));
          break;
        case "result":
          verdict = msg;
          onTaskResult?.(msg);
          break;
        case "stderr":
          stderrText += msg.data || "";
          term?.write(`${ANSI_RED}${normaliseEol(msg.data)}${ANSI_RESET}`);
          break;
        case "error":
          term?.write(`\r\n${ANSI_YELLOW}[!] ${msg.message}${ANSI_RESET}\r\n`);
          break;
        case "exit": {
          exited = true;
          const sym = msg.code === 0 ? SYM_OK : SYM_FAIL;
          term?.write(
            `\r\n${ANSI_DIM}─────────────────────────────────────────${ANSI_RESET}\r\n` +
              `${sym} exit ${msg.code} · ${Number(msg.duration || 0).toFixed(2)}s\r\n`
          );
          setLastExit({ code: msg.code, duration: msg.duration });
          const passed = verdict ? verdict.passed : msg.code === 0;
          onRunStateChange?.(passed ? "success" : "error");
          if (verdict && msg.code === 0 && !verdict.passed) {
            term?.write(
              `\r\n${ANSI_YELLOW}${t(verdict.hidden_failed ? "codeRunner.hiddenFailed" : "codeRunner.wrongOutput")}${ANSI_RESET}\r\n`
            );
          }
          // короткое пояснение Мудреца под выводом; сам вывод остаётся как есть
          if (msg.code !== 0) {
            const errType = detectErrorType(stderrText);
            if (errType) {
              // обычный абзац с отступом; перенос по ширине терминала, перевод строки с \r (иначе «лесенка»)
              const width = Math.max(28, (term?.cols || 80) - 4);
              term?.write(`\r\n${ANSI_CYAN}${t("codeRunner.errorHelp.title")}${ANSI_RESET}\r\n`);
              wrapWords(t(`codeRunner.errorHelp.${errType}`), width).forEach((line) => {
                term?.write(`  ${line}\r\n`);
              });
            }
          }
          try { ws.close(); } catch { /* noop */ }
          break;
        }
        default:
          term?.write(`${ANSI_DIM}[unknown event ${JSON.stringify(msg)}]${ANSI_RESET}\r\n`);
      }
    };

    ws.onerror = () => {
      if (userStoppedRef.current) return;
      term?.write(`\r\n${ANSI_RED}${t("codeRunner.connectLost")}${ANSI_RESET}\r\n`);
    };

    ws.onclose = (ev) => {
      wsRef.current = null;
      runLockRef.current = false;
      setRunning(false);
      if (userStoppedRef.current && !exited) {
        term?.write(`\r\n${ANSI_DIM}${t("codeRunner.stopped")}${ANSI_RESET}\r\n`);
      }
      // 4403 = refused (locked task), 4409 = a run is already going, 4429 = too many runs
      if (!exited && (ev.code === 4401 || ev.code === 4403 || ev.code === 4409 || ev.code === 4429)) {
        // refused before the code ran: no "exit" event will come
        onRunStateChange?.("error");
      }
      if (ev.code === 4401) {
        term?.write(`\r\n${ANSI_RED}[auth required — refresh login]${ANSI_RESET}\r\n`);
        toast.error(t("codeRunner.sessionExpired"));
      }
    };
  }, [running, code, task, onTaskResult, onRunStateChange, t]);

  // ── Inventory handlers ────────────────────────────────────────────────────
  const handleUseItem = useCallback(
    async (itemType, itemName) => {
      if (usingItem) return false;
      setUsingItem(true);
      try {
        const res = await Profile.consumeItem(itemType, task?.id);
        toast.success(
          t("codeRunner.itemUsed")
            .replace("{item}", itemName)
            .replace("{count}", res.remaining)
        );
        if (onInventoryUpdate) onInventoryUpdate(itemType, res.remaining);
        return res;
      } catch (error) {
        toast.error(
          error.response?.data?.detail || t("codeRunner.itemFail")
        );
        return null;
      } finally {
        setUsingItem(false);
      }
    },
    [usingItem, onInventoryUpdate, task?.id, t]
  );

  // Каркас решения приходит с сервера. Если ученик ещё ничего не менял, он заменяет
  // заготовку; иначе добавляется под его кодом, ничего не стирая и не дублируя заготовку.
  const handleSkeletonScroll = async () => {
    const res = await handleUseItem("skeleton_scrolls", t("codeRunner.items.architect"));
    if (!res?.skeleton) return;
    const starter = (task?.data?.starter || "").trim();
    const untouched = !code?.trim() || code.trim() === starter;
    onChange(
      untouched
        ? res.skeleton
        : `${code.replace(/\s+$/, "")}\n\n${t("codeRunner.skeletonDivider")}\n${res.skeleton}\n`
    );
  };

  const showHint = (hint, header) => {
    const level = hint.levels > 1 ? ` ${hint.level}/${hint.levels}` : "";
    // the terminal header is drawn with ━━━ and its own 💡; the panel has its own icon, so strip both
    const plainHeader = header.replace(/[━💡]/gu, "").trim();
    setOpenedHints((prev) => [...prev, { header: `${plainHeader}${level}`, text: hint.text }]);

    // Подсказку выводим прямо в терминал редактора — он всегда
    // привязан к панели и виден на любой ширине экрана (на 32:9
    // top-right toast визуально «уходит за экран»). Если терминал
    // ещё не смонтирован — фоллбэк на тост.
    if (termRef.current?.writeln) {
      termRef.current.writeln(`

${ANSI_YELLOW}${header}${level}${ANSI_RESET}`);
      wrapWords(hint.text, 70).forEach((line) => {
        termRef.current.writeln(`${ANSI_YELLOW}│${ANSI_RESET} ${line}`);
      });
      termRef.current.writeln(`${ANSI_YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━${ANSI_RESET}

`);
    } else {
      toast(`💡 ${hint.text}`, { duration: 6000 });
    }
  };

  const handleHintScroll = async () => {
    const res = await handleUseItem("hint_scrolls", t("codeRunner.items.clarity"));
    if (!res?.hint) return;
    showHint(res.hint, t("codeRunner.clarityHeader"));
  };

  // Бесплатная подсказка для ученика без предметов: ничего не списывается, один раз на шаг.
  // Возвращает true, если подсказка выдана.
  const handleRescueHint = async () => {
    if (usingItem) return false;
    setUsingItem(true);
    try {
      const res = await Profile.consumeItem("rescue_hint", task?.id);
      if (!res?.hint) return false;
      showHint(res.hint, t("missionPage.helpOffer.rescue"));
      return true;
    } catch (error) {
      toast.error(error.response?.data?.detail || t("codeRunner.itemFail"));
      return false;
    } finally {
      setUsingItem(false);
    }
  };

  // Баннер помощи на странице миссии вызывает те же действия, что и кнопки панели.
  useImperativeHandle(ref, () => ({
    spendHint: handleHintScroll,
    rescueHint: handleRescueHint,
    callMentor: () => setMentorOpen(true),
  }));

  const hintAvailable = Boolean(task?.data?.has_hint);
  const skeletonAvailable = Boolean(task?.data?.has_skeleton);
  const pulse = "ring-2 ring-[#e5c07b] motion-safe:animate-[pulse_2s_cubic-bezier(0.4,0,0.6,1)_4]";

  const lines = code ? code.split("\n").length : 1;
  const lineArray = Array.from({ length: Math.max(25, lines) }, (_, i) => i + 1);

  // ── клавиши редактора: Tab/Shift+Tab дают отступ, Enter сохраняет его ──────
  // Escape, а затем Tab выпускает фокус из редактора (иначе пользователь
  // клавиатуры застрял бы в нём).
  const editorRef = useRef(null);
  const gutterRef = useRef(null);
  const pendingSelection = useRef(null);
  const escapeArmed = useRef(false);

  useLayoutEffect(() => {
    const pending = pendingSelection.current;
    if (pending && editorRef.current) {
      pendingSelection.current = null;
      editorRef.current.setSelectionRange(pending.start, pending.end);
    }
  }, [code]);

  const applyEdit = (result) => {
    pendingSelection.current = { start: result.start, end: result.end };
    trackerRef.current.record("insertText", code || "", result.text);
    onChange(result.text);
  };

  const onEditorKeyDown = (e) => {
    if (e.key === "Escape") {
      escapeArmed.current = true;
      return;
    }
    const plain = !e.ctrlKey && !e.altKey && !e.metaKey;
    const { value, selectionStart, selectionEnd } = e.currentTarget;
    if (e.key === "Tab" && plain) {
      if (escapeArmed.current) {
        escapeArmed.current = false;
        return; // пусть фокус уйдёт дальше
      }
      e.preventDefault();
      applyEdit(indentAction(value, selectionStart, selectionEnd, { shift: e.shiftKey }));
      return;
    }
    escapeArmed.current = false;
    if (e.key === "Enter" && plain && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      applyEdit(newlineAction(value, selectionStart, selectionEnd));
    }
  };

  return (
    <div
      className={`flex flex-col font-mono bg-[#1e1e1e] ${
        fullscreen ? "fixed inset-0 z-[60]" : "h-full"
      }`}
    >
      {/* Editor Tabs & Toolbar */}
      <div className="flex flex-wrap items-center gap-y-1 bg-[#252526] min-w-0 select-none border-l border-[#333]">
        <div className="hidden sm:flex items-center gap-2 bg-[#1e1e1e] px-3 py-2 border-t border-[#3794ff] min-w-0 shrink-0 cursor-pointer">
          <FileCode2 size={14} className="text-[#519aba]" />
          <span className="text-xs text-white">main.py</span>
        </div>

        {/* Inventory toolbar */}
        <div className="flex items-center gap-0.5 sm:gap-1 px-1 sm:px-2 py-1 sm:border-l border-[#333] sm:ml-1 shrink-0">
          <button
            onClick={handleSkeletonScroll}
            disabled={usingItem || !inventoryCounts?.skeleton_scrolls || !skeletonAvailable}
            className={`flex items-center gap-1.5 px-2 py-2 sm:py-1 text-xs rounded transition-colors ${inventoryCounts?.skeleton_scrolls > 0 && skeletonAvailable ? "text-[#e5c07b] hover:bg-[#333] cursor-pointer" : "text-[#8a8a8a] cursor-not-allowed"}`}
            title={skeletonAvailable ? t("codeRunner.items.architect") : t("codeRunner.items.noSkeleton")}
            aria-label={`${t("codeRunner.items.architectCount").replace("{n}", inventoryCounts?.skeleton_scrolls || 0)}${skeletonAvailable ? "" : `. ${t("codeRunner.items.noSkeleton")}`}`}
          >
            <Scroll size={14} aria-hidden="true" />
            <span aria-hidden="true">{inventoryCounts?.skeleton_scrolls || 0}</span>
            <span className="hidden 2xl:inline" aria-hidden="true">{t("codeRunner.items.architectShort")}</span>
          </button>

          <button
            onClick={handleHintScroll}
            disabled={usingItem || !inventoryCounts?.hint_scrolls || !hintAvailable}
            className={`flex items-center gap-1.5 px-2 py-2 sm:py-1 text-xs rounded transition-colors ${inventoryCounts?.hint_scrolls > 0 && hintAvailable ? "text-[#98c379] hover:bg-[#333] cursor-pointer" : "text-[#8a8a8a] cursor-not-allowed"} ${pulseHelp && hintAvailable && inventoryCounts?.hint_scrolls > 0 ? pulse : ""}`}
            title={hintAvailable ? t("codeRunner.items.clarity") : t("codeRunner.items.noHint")}
            aria-label={`${t("codeRunner.items.clarityCount").replace("{n}", inventoryCounts?.hint_scrolls || 0)}${hintAvailable ? "" : `. ${t("codeRunner.items.noHint")}`}`}
          >
            <Lightbulb size={14} aria-hidden="true" />
            <span aria-hidden="true">{inventoryCounts?.hint_scrolls || 0}</span>
            <span className="hidden 2xl:inline" aria-hidden="true">{t("codeRunner.items.clarityShort")}</span>
          </button>

          <button
            onClick={() => setMentorOpen(true)}
            className={`flex items-center gap-1.5 px-2 py-2 sm:py-1 text-xs rounded transition-colors text-[#c678dd] hover:bg-[#333] cursor-pointer ${pulseHelp && inventoryCounts?.ai_summons > 0 ? pulse : ""}`}
            title={t("codeRunner.mentor.open")}
            aria-label={t("codeRunner.items.mentorCount").replace("{n}", inventoryCounts?.ai_summons || 0)}
          >
            <Bot size={14} aria-hidden="true" />
            <span aria-hidden="true">{inventoryCounts?.ai_summons || 0}</span>
            <span className="hidden 2xl:inline" aria-hidden="true">{t("codeRunner.items.mentorShort")}</span>
          </button>
        </div>

        <div className="flex-1 min-w-0" />
        <div className="pl-1 pr-3 sm:pl-2 sm:pr-4 py-0.5 flex items-center gap-1.5 sm:gap-2 bg-[#252526] shrink-0">
          {/* Развернуть редактор на весь экран / свернуть обратно. */}
          <button
            onClick={() => setFullscreen((v) => !v)}
            title={fullscreen ? t("codeRunner.exitFullscreen") : t("codeRunner.fullscreen")}
            aria-label={fullscreen ? t("codeRunner.exitFullscreen") : t("codeRunner.fullscreen")}
            className="grid h-7 w-7 place-items-center rounded border border-[#3a3a3a] bg-[#2d2d2d] text-[#cccccc] hover:bg-[#3a3a3a] hover:text-white transition-colors"
          >
            {fullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>

          {/* Reset code — всегда активна, не тратит инвентарь.
              Возвращает к initialCodeRef (стартеру задачи). */}
          {/* Кнопки в стиле мокапа Codemancer: «самоцветы» с фаской —
              RUN зелёный, RESET красно-коричневый, STOP глубокий багровый. */}
          <button
            onClick={handleResetCode}
            title={t("codeRunner.resetTitle")}
            aria-label={t("codeRunner.resetTitle")}
            className="flex items-center gap-1.5 px-2.5 py-2 sm:py-1 rounded border border-[#a0432a] bg-gradient-to-b from-[#7a2b1a] to-[#3a0d06] hover:from-[#8e3420] hover:to-[#4a1208] text-[#f3e6c2] text-xs transition-colors shadow-[inset_0_1px_0_rgba(255,220,140,0.2)]"
          >
            <RotateCcw size={11} />
            <span className="hidden 2xl:inline">{t("codeRunner.reset")}</span>
          </button>

          {running ? (
            <button
              onClick={stopRun}
              className="flex items-center gap-1.5 px-3 py-2 sm:py-1 rounded border border-[#d14a4a] bg-gradient-to-b from-[#a31515] to-[#5e0c0c] hover:from-[#c41a1a] hover:to-[#6e0e0e] text-white text-xs transition-colors shadow-[inset_0_1px_0_rgba(255,200,200,0.2)]"
            >
              <Square size={11} fill="currentColor" />
              {t("codeRunner.stop")}
            </button>
          ) : (
            <button
              onClick={runCode}
              className="flex items-center gap-1.5 px-3 py-2 sm:py-1 rounded border border-[#5a8a2a] bg-gradient-to-b from-[#3a6a22] to-[#1b3a0e] hover:from-[#46802a] hover:to-[#224a12] text-[#f1ffd6] text-xs transition-colors shadow-[inset_0_1px_0_rgba(255,220,140,0.25)]"
            >
              <Play size={12} fill="currentColor" />
              {t("codeRunner.run")}
            </button>
          )}
        </div>
      </div>

      {/* Breadcrumbs */}
      <div className="hidden sm:flex items-center gap-1.5 px-4 py-1.5 text-xs text-[#cccccc] bg-[#1e1e1e] border-b border-[#333] border-l select-none shadow-sm z-10">
        <span className="hover:text-white cursor-pointer">{t("codeRunner.crumbRoot")}</span>
        <span className="opacity-50">&gt;</span>
        <span className="hover:text-white cursor-pointer">{t("codeRunner.crumbMission")}</span>
        <span className="opacity-50">&gt;</span>
        <span className="hover:text-white cursor-pointer">{t("codeRunner.crumbFile")}</span>
      </div>

      {openedHints.length > 0 && (
        <div
          role="region"
          aria-label={t("codeRunner.hintsPanel")}
          className="max-h-32 shrink-0 space-y-2 overflow-y-auto border-l border-[#333] bg-[#2a2415] px-4 py-2 text-xs text-[#e5c07b]"
        >
          {openedHints.map((h, i) => (
            <p key={i} className="leading-snug">
              <span className="font-bold">💡 {h.header}: </span>
              {h.text}
            </p>
          ))}
        </div>
      )}

      {/* Editor */}
      <div className="flex-1 relative bg-[#1e1e1e] flex border-l border-[#333] min-h-[140px]">
        <div
          ref={gutterRef}
          aria-hidden="true"
          className="w-12 bg-[#1e1e1e] border-r border-[#333] flex flex-col items-end py-4 pr-3 text-[#9da3ab] text-xs select-none overflow-hidden font-mono"
        >
          {lineArray.map((n) => (
            <span key={n} className="leading-6">{n}</span>
          ))}
        </div>
        <textarea
          ref={editorRef}
          value={code || ""}
          onChange={(e) => {
            trackerRef.current.record(e.nativeEvent?.inputType, code || "", e.target.value);
            onChange(e.target.value);
          }}
          onPaste={(e) => trackerRef.current.paste(e.clipboardData?.getData("text")?.length || 0)}
          onKeyDown={onEditorKeyDown}
          // номера строк едут вместе с текстом, иначе «ошибка в строке N» врёт
          onScroll={(e) => {
            if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop;
          }}
          spellCheck="false"
          // на телефоне первая буква не должна становиться заглавной: Print(...) — это NameError
          autoCapitalize="off"
          autoCorrect="off"
          autoComplete="off"
          aria-label={t("codeRunner.editorLabel")}
          aria-describedby="editor-keys-hint"
          className="w-full h-full p-4 bg-transparent text-[13px] font-mono text-[#d4d4d4] resize-none focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#d9a441] leading-6"
          placeholder={t("codeRunner.placeholder")}
        />
        <span id="editor-keys-hint" className="sr-only">
          {t("codeRunner.editorHint")}
        </span>
      </div>

      {/* Drag handle — только когда терминал развёрнут */}
      {!termCollapsed && (
        <div
          ref={dragRef}
          onPointerDown={onDragStart}
          className="h-3 sm:h-2 touch-none bg-[#252526] border-t border-b border-[#333] flex items-center justify-center cursor-row-resize hover:bg-[#2a2d2e] select-none group"
          title={t("codeRunner.resizeTitle")}
        >
          <GripHorizontal size={12} className="text-[#555] group-hover:text-[#888]" />
        </div>
      )}

      {/* Terminal — adaptive height, сворачиваемый (xterm остаётся смонтирован) */}
      <div
        style={termCollapsed ? undefined : { height: termH, maxHeight: "45%" }}
        className="flex flex-col bg-[#1e1e1e] border-l border-[#333] flex-shrink-0"
      >
        <div className="flex items-center gap-4 px-4 pt-2 border-b border-[#333] select-none">
          <span className="text-xs uppercase tracking-wider text-white border-b border-white pb-2 font-semibold flex items-center gap-2">
            <TerminalIcon size={14} /> {t("codeRunner.terminal")}
          </span>
          {running && (
            <span className="text-xs tracking-wider text-[#cca700] pb-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#cca700] animate-pulse" />
              running…
            </span>
          )}
          {!running && lastExit && (
            <span className={`text-xs tracking-wider pb-2 ${lastExit.code === 0 ? "text-[#23d18b]" : "text-[#f14c4c]"}`}>
              exit {lastExit.code} · {Number(lastExit.duration || 0).toFixed(2)}s
            </span>
          )}
          <div className="flex-1" />
          <button
            onClick={() => setTermCollapsed((v) => !v)}
            title={termCollapsed ? t("codeRunner.terminalExpand") : t("codeRunner.terminalCollapse")}
            aria-label={termCollapsed ? t("codeRunner.terminalExpand") : t("codeRunner.terminalCollapse")}
            className="mb-1 grid h-6 w-6 place-items-center rounded text-[#888] hover:bg-[#333] hover:text-white transition-colors"
          >
            {termCollapsed ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
        <div className={`min-h-0 ${termCollapsed ? "h-0 overflow-hidden p-0" : "flex-1 p-2"}`}>
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

export default forwardRef(CodeRunnerPanel);
