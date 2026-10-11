import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Lock, CheckCircle, Compass, ChevronRight, Map } from "lucide-react";
import { missionStatus } from "../lib/api";
import { lockReason, missionTitle, missionXp } from "../lib/missions";
import { useI18n } from "../lib/i18n";
import Reveal from "./Reveal";
import EmptyScroll, { SkeletonScroll } from "./EmptyScroll";

// Курсы идут подряд: у каждого своя тропа под своим названием.
function byCourse(missions) {
  const groups = [];
  missions.forEach((mission) => {
    const last = groups[groups.length - 1];
    if (last && last.trackId === mission.track_id) last.items.push(mission);
    else groups.push({ trackId: mission.track_id, title: mission.track_title || "", items: [mission] });
  });
  return groups;
}

/**
 * Карта миров на телефоне: вертикальная тропа вместо горизонтальной карты с наведением.
 * Сверху общий прогресс, текущая миссия выделена, у закрытой написано, чего не хватает.
 */
export default function MissionPath({ missions, loading }) {
  const { t, language } = useI18n();
  const currentRef = useRef(null);
  const [barReady, setBarReady] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setBarReady(true), 80);
    return () => clearTimeout(timer);
  }, []);

  const total = missions.length;
  const done = missions.filter((m) => missionStatus(m) === "completed").length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const current = missions.find((m) => missionStatus(m) === "available");

  // длинный список открываем сразу на текущей миссии
  useEffect(() => {
    if (loading || !current || !currentRef.current) return;
    if (missions.indexOf(current) > 2) currentRef.current.scrollIntoView({ block: "center" });
    // только при смене текущей миссии: иначе список прыгал бы при каждом обновлении данных
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, current?.id]);

  if (loading) {
    return (
      <SkeletonScroll label={t("worldsPage.mapLoading")} rows={5} className="lg:hidden px-4 pt-2 pb-16" />
    );
  }

  if (!total) {
    return (
      <div className="lg:hidden px-4 py-8">
        <EmptyScroll icon={Map}>{t("worldsPage.mapEmpty")}</EmptyScroll>
      </div>
    );
  }

  const renderMission = (mission, index, count) => {
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
    const reason = isLocked ? lockReason(mission, missions, t) : "";
    const steps = (mission.tasks || []).length;
    const totalXp = missionXp(mission);
    const meta = [
      totalXp ? t("worldsPage.mobile.reward").replace("{xp}", totalXp) : "",
      steps ? t("worldsPage.mobile.steps").replace("{n}", steps) : "",
    ]
      .filter(Boolean)
      .join(" · ");

    const body = (
      <>
        <span className="min-w-0 flex-1">
          <span className="block font-display font-bold leading-snug text-text line-clamp-2">{title}</span>
          <span
            className={`mt-0.5 block text-xs font-bold uppercase tracking-widest ${
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
      <Reveal
        as="li"
        key={mission.id}
        delay={Math.min(index, 6) * 60}
        className="relative flex gap-3 pb-3 last:pb-0"
      >
        <span ref={isCurrent ? currentRef : undefined} className="absolute inset-y-0 left-0 w-0" aria-hidden="true" />
        {index < count - 1 && (
          <span
            aria-hidden="true"
            className={`absolute left-[21px] top-11 bottom-0 w-0.5 ${isCompleted ? "bg-emerald-500/60" : "bg-border"}`}
          />
        )}
        <span
          className={`relative z-10 grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 bg-bg ${
            isCompleted
              ? "border-emerald-500/60 text-emerald-700 dark:text-emerald-400"
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
      </Reveal>
    );
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
          <div className="h-full w-full origin-left bg-primary transition-transform duration-700" style={{ transform: `scaleX(${(barReady ? pct : 0) / 100})` }} />
        </div>
      </div>

      {byCourse(missions).map((group, groupIndex) => (
        <section key={group.trackId ?? `group-${groupIndex}`} className={groupIndex ? "mt-8" : ""}>
          {group.title ? (
            <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-muted">{group.title}</h2>
          ) : null}
          <ol>{group.items.map((mission, index) => renderMission(mission, index, group.items.length))}</ol>
        </section>
      ))}
    </div>
  );
}
