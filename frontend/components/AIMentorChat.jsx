/**
 * AIMentorChat — Codemancer-styled conversational mentor ("The Sage").
 *
 * A non-modal drawer that slides in from the right edge of the mission page.
 * Unlike the old single-shot hint (dumped into the terminal), this is a real
 * conversation: it keeps history client-side and sends it — together with the
 * current editor code and task description — to POST /api/game/ai-mentor/.
 *
 * Each successful reply costs 1 ai_summon (mana); the count is reported back
 * via onInventoryUpdate so the HUD's MP bar drains as the student consults
 * the Sage. The panel stays usable (read-only) at 0 mana.
 *
 * Props:
 *   open               — whether the drawer is visible
 *   onClose            — close the drawer
 *   task               — active task (source of description + language)
 *   code               — current editor code (grounding context)
 *   summons            — remaining ai_summons (mana)
 *   onInventoryUpdate  — (itemType, remaining) => void, syncs HUD/inventory
 */

import { useEffect, useRef, useState } from "react";
import { Droplet, Loader2, Send, X } from "lucide-react";
import { toast } from "sonner";
import { AIAssist } from "../lib/api";
import { useI18n } from "../lib/i18n";

// Маленький пиксель-маг — узнаваемый аватар Мудреца в стиле сцены Codemancer.
function SageAvatar({ className = "" }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true">
      <rect width="40" height="40" rx="9" fill="#0f2421" />
      <rect width="40" height="40" rx="9" fill="url(#cm-sage-glow)" opacity=".5" />
      <defs>
        <radialGradient id="cm-sage-glow" cx=".5" cy=".35" r=".6">
          <stop offset="0" stopColor="#d9a441" stopOpacity=".45" />
          <stop offset="1" stopColor="#d9a441" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* hood */}
      <path d="M20 7 L32 31 H8 Z" fill="#1e5245" />
      <path d="M20 7 L26 19 H14 Z" fill="#2f7a66" />
      {/* face */}
      <rect x="15" y="18" width="10" height="9" fill="#f0c79a" />
      {/* glowing eyes */}
      <rect x="16.5" y="21" width="2" height="2" fill="#ffe066" />
      <rect x="21.5" y="21" width="2" height="2" fill="#ffe066" />
      {/* beard */}
      <path d="M15 27 h10 l-2 5 h-6 z" fill="#E8F0EA" />
      {/* sparkle on the hood tip */}
      <circle cx="20" cy="7" r="1.6" fill="#ffe066" />
    </svg>
  );
}

export default function AIMentorChat({
  open,
  onClose,
  task,
  code,
  summons = 0,
  onInventoryUpdate,
}) {
  const { t } = useI18n();
  const [messages, setMessages] = useState([]); // {role:'user'|'assistant', content}
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const taskDesc =
    task?.body_ru || task?.body_en || task?.data?.hint || task?.title_ru || "";
  const language = task?.data?.language || "python";

  const hasMana = summons > 0;
  const canSend = open && !loading && hasMana && draft.trim().length > 0;

  // Автопрокрутка к последней реплике при изменении ленты / индикатора печати.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading, open]);

  // Фокус в поле ввода при открытии (если мана есть).
  useEffect(() => {
    if (open && hasMana) {
      const id = setTimeout(() => inputRef.current?.focus(), 320);
      return () => clearTimeout(id);
    }
  }, [open, hasMana]);

  // Esc закрывает свиток Мудреца (запасной выход помимо крестика).
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const send = async () => {
    const content = draft.trim();
    if (!content || loading) return;
    if (!hasMana) {
      toast.error(t("codeRunner.mentor.noMana"));
      return;
    }

    const nextHistory = [...messages, { role: "user", content }];
    setMessages(nextHistory);
    setDraft("");
    setLoading(true);

    try {
      const { reply, remaining_summons } = await AIAssist.mentor(
        nextHistory,
        code || "",
        taskDesc,
        language,
        task?.id
      );
      setMessages([...nextHistory, { role: "assistant", content: reply }]);
      if (onInventoryUpdate && remaining_summons !== undefined) {
        onInventoryUpdate("ai_summons", remaining_summons);
      }
    } catch (err) {
      const data = err?.response?.data;
      // 402 (мана кончилась) синхронизируем счётчик HUD к нулю.
      if (data?.remaining_summons !== undefined && onInventoryUpdate) {
        onInventoryUpdate("ai_summons", data.remaining_summons);
      }
      const detail = data?.detail || t("codeRunner.mentor.error");
      toast.error(detail);
      // Возвращаем неотправленный текст, чтобы ученик не потерял вопрос.
      setMessages(messages);
      setDraft(content);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) send();
    }
  };

  return (
    <div
      className={`fixed inset-y-0 right-0 z-[120] flex w-full max-w-md flex-col border-l border-[#d9a441]/30 bg-gradient-to-b from-[#0f2421] to-[#06100D] shadow-[-16px_0_50px_rgba(0,0,0,0.55)] transition-transform duration-300 ease-out ${
        open ? "translate-x-0" : "pointer-events-none translate-x-full"
      }`}
      role="dialog"
      aria-modal="false"
      aria-label={t("codeRunner.mentor.title")}
      aria-hidden={!open}
    >
      {/* верхняя золотая линия — рамка свитка */}
      <div className="h-[3px] w-full bg-gradient-to-r from-transparent via-[#d9a441]/70 to-transparent" />

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#d9a441]/20">
        <SageAvatar className="w-10 h-10 shrink-0 rounded-[9px] shadow-[0_0_14px_rgba(217,164,65,0.35)]" />
        <div className="min-w-0">
          <div className="font-display text-[15px] leading-tight text-parchment-pale">
            {t("codeRunner.mentor.title")}
          </div>
          <div className="text-xs uppercase tracking-[0.18em] text-[#d9a441]/80">
            {t("codeRunner.mentor.subtitle")}
          </div>
        </div>
        <div className="flex-1" />
        {/* Мана (ai_summons) */}
        <div
          className="flex items-center gap-1.5 rounded-lg border border-[#4ade80]/25 bg-[#0b1a17] px-2.5 py-1"
          title={t("codeRunner.mentor.mana")}
        >
          <Droplet size={13} className="text-[#4ade80]" fill="#4ade80" />
          <span className="text-[12px] font-semibold text-[#d7f5e3] tabular-nums">
            {summons}
          </span>
        </div>
        <button
          onClick={onClose}
          aria-label={t("codeRunner.mentor.close")}
          title={t("codeRunner.mentor.close")}
          className="ml-1 grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-[#c6d6cf] transition-colors hover:border-[#d9a441]/50 hover:bg-white/10 hover:text-white"
        >
          <X size={18} />
        </button>
      </div>

      {/* ── Messages ───────────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {/* приветствие Мудреца (только для отображения, не уходит в историю) */}
        <MageBubble text={t("codeRunner.mentor.greeting")} />

        {messages.map((m, i) =>
          m.role === "user" ? (
            <UserBubble key={i} text={m.content} />
          ) : (
            <MageBubble key={i} text={m.content} />
          )
        )}

        {loading && (
          <div className="mr-auto flex max-w-[85%] items-center gap-2 rounded-2xl rounded-tl-sm bg-parchment-wash px-3.5 py-2.5 text-[#5a4a2a] shadow">
            <Loader2 size={14} className="animate-spin" />
            <span className="text-[13px]">{t("codeRunner.mentor.thinking")}</span>
          </div>
        )}
      </div>

      {/* ── Composer ───────────────────────────────────────────── */}
      <div className="border-t border-[#d9a441]/20 p-3">
        {!hasMana && (
          <p className="mb-2 px-1 text-[12px] leading-snug text-[#e3b9b9]">
            {t("codeRunner.mentor.noMana")}
          </p>
        )}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={loading || !hasMana}
            rows={2}
            spellCheck="false"
            placeholder={t("codeRunner.mentor.placeholder")}
            className="min-h-[44px] max-h-32 flex-1 resize-none rounded-xl border border-white/10 bg-[#0b1a17] px-3 py-2 text-[13px] leading-relaxed text-[#E8F0EA] placeholder:text-[#7f978d] focus:border-[#d9a441]/50 focus:outline-none focus:ring-0 disabled:opacity-50"
          />
          <button
            onClick={send}
            disabled={!canSend}
            aria-label={t("codeRunner.mentor.send")}
            className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl transition-colors ${
              canSend
                ? "bg-[#d9a441] text-[#1a1206] hover:bg-[#e6b455]"
                : "cursor-not-allowed bg-[#1e3a33] text-[#7f978d]"
            }`}
          >
            {loading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={17} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Реплика Мудреца — пергаментный «свиток».
function MageBubble({ text }) {
  return (
    <div className="mr-auto max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-tl-sm bg-parchment-wash px-3.5 py-2.5 text-[13px] leading-relaxed text-[#2c2114] shadow">
      {text}
    </div>
  );
}

// Реплика ученика — тёмный сланцевый пузырь.
function UserBubble({ text }) {
  return (
    <div className="ml-auto max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm border border-white/5 bg-[#16302a] px-3.5 py-2.5 text-[13px] leading-relaxed text-[#E8F0EA] shadow">
      {text}
    </div>
  );
}
