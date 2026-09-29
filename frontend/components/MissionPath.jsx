import { useEffect, useRef } from "react";
import Link from "next/link";
import { Lock, CheckCircle, Compass, ChevronRight } from "lucide-react";
import { missionStatus } from "../lib/api";
import { useI18n } from "../lib/i18n";

const missionTitle = (mission, language, fallback) =>
  (language === "en"
    ? mission.title_en || mission.title_ru
    : mission.title_ru || mission.title_en) ||
  mission.title ||
  mission.name ||
  fallback;

/**
 * Карта миров на телефоне: вертикальная тропа вместо горизонтальной карты с наведением.
 * Сверху общий прогресс, текущая миссия выделена, у закрытой написано, чего не хватает.
 */
export default function MissionPath({ missions, loading }) {
  const { t, language } = useI18n();
  const currentRef = useRef(null);

  const total = missions.length;
  const done = missions.filter((m) => missionStatus(m) === "completed").length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const current = missions.find((m) => missionStatus(m) === "available");
  const byId = Object.fromEntries(missions.map((m) => [m.id, m]));

  // длинный список открываем сразу на текущей миссии
  useEffect(() => {
    if (loading || !current || !currentRef.current) return;
    if (missions.indexOf(current) > 2) currentRef.current.scrollIntoView({ block: "center" });
  }, [loading, current?.id]);

  if (loading) {
    return (
      <div className="lg:hidden space-y-3 px-4 pt-2 pb-16">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-[68px] rounded-2xl bg-panel border border-border animate-pulse" />
        ))}
      </div>
    );
  }

  if (!total) {
    return (
      <div className="lg:hidden px-4 py-12 text-center font-display font-bold text-muted">
        {t("worldsPage.mapEmpty")}
      </div>
    );
  }

  // Что мешает открыть миссию: незавершённая предыдущая или недостающий уровень.
  const lockReason = (mission) => {
    const open = (mission.prerequisites || []).find((pre) => missionStatus(byId[pre.id] || {}) !== "completed");
    if (open) return t("worldsPage.mobile.lockedAfter").replace("{title}", open.title);
    if (mission.min_level > 1) return t("worldsPage.mobile.lockedLevel").replace("{n}", mission.min_level);
    return "";
  };

  return (
    <div className="lg:hidden px-4 pt-2 pb-16">
      <div className="mb-5 rounded-2xl border border-border bg-panel p-4">
        <div className="flex items-baseline justify-between gap-3">
          <p className="font-display font-bold text-text">
            {t("worldsPage.mobile.progress").replace("{done}", done).replace("{total}", total)}
          </p>
          <span className="text-sm font-bold text-muted">{pct}%</span>
        </div>
        <div
          role="progressbar"
          aria-label={t("worldsPage.mobile.progressLabel")}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={done}
          className="mt-3 h-2 overflow-hidden rounded-full bg-border"
        >
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <ol>
        {missions.map((mission, index) => {
          const status = missionStatus(mission);
          const isCompleted = status === "completed";
          const isLocked = status === "locked";
          const isCurrent = mission.id === current?.id;
          const started = mission.user_progress?.status === "in_progress";
          const Icon = isCompleted ? CheckCircle : isLocked ? Lock : Compass;
          const title = missionTitle(mission, language, t("worldsPage.missionFallback"));
          const statusLabel = isCompleted
            ? t("worldsPage.statusCompleted")
            : isLocked
            ? t("worldsPage.statusLocked")
            : isCurrent
            ? t(started ? "worldsPage.mobile.continue" : "worldsPage.mobile.start")
            : t("worldsPage.statusAvailable");
          const reason = isLocked ? lockReason(mission) : "";
          const steps = (mission.tasks || []).length;
          const meta = [
            mission.xp_reward ? t("worldsPage.mobile.reward").replace("{xp}", mission.xp_reward) : "",
            steps ? t("worldsPage.mobile.steps").replace("{n}", steps) : "",
          ]
            .filter(Boolean)
            .join(" · ");

          const body = (
            <>
              <span className="min-w-0 flex-1">
                <span className="block font-display font-bold leading-snug text-text line-clamp-2">
                  {title}
                </span>
                <span
                  className={`mt-0.5 block text-[11px] font-bold uppercase tracking-widest ${
                    isCurrent ? "text-primary" : "text-muted"
                  }`}
                >
                  {statusLabel}
                </span>
                {reason && <span className="mt-1 block text-xs leading-snug text-muted">{reason}</span>}
                {!isLocked && meta && <span className="mt-1 block text-xs text-muted">{meta}</span>}
              </span>
              {!isLocked && <ChevronRight size={18} aria-hidden="true" className="shrink-0 text-muted" />}
            </>
          );
          const cardClass = `flex min-h-[64px] flex-1 min-w-0 items-center gap-3 rounded-2xl border p-3 transition-colors ${
            isLocked
              ? "border-border bg-panel/60 opacity-75"
              : isCurrent
              ? "border-primary bg-primary/10 shadow-glow"
              : "border-border bg-surface active:scale-[0.99] hover:border-primary/50"
          }`;

          return (
            <li key={mission.id} ref={isCurrent ? currentRef : undefined} className="relative flex gap-3 pb-3 last:pb-0">
              {index < total - 1 && (
                <span
                  aria-hidden="true"
                  className={`absolute left-[21px] top-11 bottom-0 w-0.5 ${isCompleted ? "bg-emerald-500/60" : "bg-border"}`}
                />
              )}
              <span
                className={`relative z-10 grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 bg-bg ${
                  isCompleted
                    ? "border-emerald-500/60 text-emerald-600 dark:text-emerald-400"
                    : isLocked
                    ? "border-border text-muted"
                    : "border-primary text-primary"
                }`}
              >
                {isCurrent && (
                  <span className="absolute inset-0 rounded-full bg-primary/30 animate-ping motion-reduce:animate-none" />
                )}
                <Icon size={20} strokeWidth={2.2} aria-hidden="true" className="relative" />
              </span>
              {isLocked ? (
                <div className={cardClass}>{body}</div>
              ) : (
                <Link href={`/missions/${mission.id}`} className={cardClass}>
                  {body}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
