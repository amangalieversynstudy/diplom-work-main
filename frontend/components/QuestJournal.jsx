import { useId, useState } from "react";
import Link from "next/link";
import { BookOpen, ChevronDown } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { missionStatus } from "../lib/api";
import { lockReason, missionTitle, missionXp } from "../lib/missions";

/**
 * Журнал квестов над картой: «Сейчас» (текущая миссия), «Дальше» (следующая по порядку)
 * и «Цель дня». Всё считается из уже загруженного списка миссий; на телефоне свёрнут.
 */
export default function QuestJournal({ missions, current }) {
  const { t, language } = useI18n();
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  if (!missions.length) return null;

  const fallback = t("worldsPage.missionFallback") || "";
  const index = current ? missions.findIndex((m) => m.id === current.id) : -1;
  const next = missions.slice(index + 1).find((m) => missionStatus(m) !== "completed") || null;
  const resume = current?.user_progress?.status === "in_progress";

  return (
    <section
      aria-label={t("worldsPage.journal.title")}
      className="mt-2 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 sm:px-6 sm:py-4 lg:mt-0"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex w-full items-center justify-between gap-2 text-left lg:pointer-events-none"
      >
        <span className="inline-flex items-center gap-2 font-title text-xl text-text">
          <BookOpen size={18} aria-hidden="true" className="text-primary" />
          {t("worldsPage.journal.title")}
        </span>
        <ChevronDown
          size={18}
          aria-hidden="true"
          className={`text-primary transition-transform motion-reduce:transition-none lg:hidden ${open ? "rotate-180" : ""}`}
        />
      </button>

      <div id={bodyId} className={`${open ? "grid" : "hidden"} mt-3 gap-3 lg:grid lg:grid-cols-[1.4fr_1fr_1fr] lg:items-stretch`}>
        <div className="flex min-w-0 items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-widest text-primary">{t("worldsPage.journal.now")}</p>
            {current ? (
              <>
                <p className="mt-1 truncate font-display text-lg font-bold text-text">
                  {missionTitle(current, language, fallback)}
                </p>
                <p className="mt-0.5 text-sm text-muted">
                  {t("worldsPage.mobile.reward").replace("{xp}", missionXp(current))}
                </p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted">{t("worldsPage.journal.nothing")}</p>
            )}
          </div>
          {current ? (
            <Link
              href={`/missions/${current.id}`}
              className="inline-flex min-h-[44px] shrink-0 items-center justify-center rounded-full bg-primary px-5 py-2 text-sm font-semibold text-on-primary shadow-glow transition hover:bg-primary-dk"
            >
              {t(resume ? "worldsPage.mobile.continue" : "worldsPage.mobile.start")}
            </Link>
          ) : null}
        </div>

        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">{t("worldsPage.journal.later")}</p>
          {next ? (
            <>
              <p className="mt-1 truncate font-display text-base font-bold text-text">
                {missionTitle(next, language, fallback)}
              </p>
              {missionStatus(next) === "locked" ? (
                <p className="mt-0.5 truncate text-xs italic text-muted">{lockReason(next, missions, t)}</p>
              ) : null}
            </>
          ) : (
            <p className="mt-1 text-sm text-muted">{t("worldsPage.journal.laterNone")}</p>
          )}
        </div>

        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">{t("worldsPage.journal.goal")}</p>
          <p className="mt-1 text-sm leading-snug text-text">{t("worldsPage.journal.goalText")}</p>
        </div>
      </div>
    </section>
  );
}
