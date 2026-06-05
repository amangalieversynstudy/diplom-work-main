import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { Flame, X } from "lucide-react";
import { Profile as ProfileAPI } from "../lib/api";
import { useI18n } from "../lib/i18n";
import logger from "../lib/logger";

// Локальная дата в формате YYYY-MM-DD — ключ «скрыто на сегодня».
function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

/**
 * Плавающее напоминание о стрике. Показывается, только если бэкенд
 * пометил серию как streak_at_risk («жива, но сегодня ещё не продлена»).
 * Фиксированное позиционирование — не влияет на верстку/расчёты страниц
 * (например, GSAP-пиннинг карты миров). Скрытие запоминается до конца дня.
 */
export default function StreakReminder() {
  const router = useRouter();
  const { t } = useI18n();
  const [info, setInfo] = useState(null); // { current, atRisk }
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const hasToken =
      typeof window !== "undefined" &&
      (localStorage.getItem("access_token") || localStorage.getItem("access"));
    if (!hasToken) return; // гостям ничего не грузим

    (async () => {
      try {
        const me = await ProfileAPI.me();
        const p = me?.profile ?? me ?? {};
        if (cancelled) return;
        setInfo({
          current: p.current_streak ?? 0,
          atRisk: !!p.streak_at_risk,
        });
        const dismissed =
          localStorage.getItem("streak_reminder_dismissed") === todayKey();
        setHidden(dismissed);
      } catch (e) {
        // Напоминание — необязательный путь: молча не показываем при ошибке.
        logger.error("Streak reminder load failed:", e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!info || !info.atRisk || hidden) return null;

  const dismiss = () => {
    try {
      localStorage.setItem("streak_reminder_dismissed", todayKey());
    } catch {
      /* localStorage может быть недоступен — не критично */
    }
    setHidden(true);
  };

  return (
    <div
      role="status"
      className="fixed bottom-4 left-1/2 z-40 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-center gap-3 rounded-2xl border border-orange-500/30 bg-surface/95 px-4 py-3 shadow-lg backdrop-blur-xl"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-orange-500/15">
        <Flame size={20} className="text-orange-500" fill="currentColor" />
      </span>
      <p className="flex-1 text-sm leading-snug text-text">
        {t("streak.reminder.banner").replace("{n}", info.current)}
      </p>
      <button
        type="button"
        onClick={() => router.push("/worlds")}
        className="shrink-0 rounded-xl bg-orange-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-orange-600"
      >
        {t("streak.reminder.cta")}
      </button>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t("streak.reminder.dismiss")}
        className="shrink-0 text-muted transition-colors hover:text-text"
      >
        <X size={18} />
      </button>
    </div>
  );
}
