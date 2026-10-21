import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Award, Flame, Sparkles, Star, TrendingUp } from "lucide-react";
import Button from "./Button";
import { useDialog } from "../lib/useDialog";
import { useI18n } from "../lib/i18n";
import { prefersReducedMotion } from "../lib/motion";

const MAX_STARS = 3;

// Число XP «набегает» от нуля; при reduced-motion сразу показываем итог.
function useCountUp(target, active) {
  const [value, setValue] = useState(target);
  useEffect(() => {
    if (!active || !(target > 0) || prefersReducedMotion()) {
      setValue(target);
      return undefined;
    }
    let frame;
    const start = performance.now();
    const duration = 900;
    setValue(0);
    const tick = (now) => {
      const k = Math.min(1, (now - start) / duration);
      setValue(Math.round(target * k));
      if (k < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active]);
  return value;
}

function LootRow({ icon: Icon, children, strong = false }) {
  return (
    <li className="flex items-center gap-3 rounded-xl border border-[color:var(--gold-frame)]/60 bg-panel px-4 py-2 text-left">
      <Icon size={20} aria-hidden="true" className="shrink-0 text-primary" />
      <span className={strong ? "font-display text-xl font-bold text-primary" : "text-sm font-semibold text-text"}>
        {children}
      </span>
    </li>
  );
}

/**
 * Окно «миссия пройдена»: итог, звёзды и куда идти дальше. Закрывается Esc,
 * кликом по фону или кнопкой «Остаться».
 */
export default function MissionComplete({ data, onClose, onMap }) {
  const { t } = useI18n();
  const ref = useRef(null);
  const titleId = useId();
  useDialog(Boolean(data), ref, onClose);
  // пока открыто окно, всплывающие уведомления прячем: всё, что они говорят, уже в окне
  const open = Boolean(data);
  useEffect(() => {
    if (!open) return undefined;
    document.documentElement.classList.add("loot-open");
    return () => document.documentElement.classList.remove("loot-open");
  }, [open]);
  const xpShown = useCountUp(data?.xp > 0 ? data.xp : 0, Boolean(data));
  if (!data) return null;

  const stars = Math.max(0, Math.min(MAX_STARS, Number(data.stars) || 0));
  const starsText = t("missionPage.complete.starsEarned").replace("{n}", stars).replace("{max}", MAX_STARS);

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm"
      // закрытие по фону только когда нажали именно на фон; с клавиатуры есть Esc и кнопка «Остаться»
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="complete-card scroll-frame max-h-[calc(100dvh-2rem)] w-full max-w-xl overflow-y-auto p-6 text-center text-card-text sm:p-8"
      >
        <div
          className="mb-4 flex justify-center gap-2"
          role="img"
          aria-label={t("missionPage.complete.starsLabel").replace("{n}", stars).replace("{max}", MAX_STARS)}
        >
          {Array.from({ length: MAX_STARS }).map((_, i) => (
            <Star
              key={i}
              size={40}
              aria-hidden="true"
              style={{ animationDelay: `${250 + i * 220}ms` }}
              className={`star-pop ${i < stars ? "fill-warning text-warning" : "text-border"}`}
            />
          ))}
        </div>
        <h2 id={titleId} className="font-title text-3xl">
          {t("missionPage.complete.loot")}
        </h2>
        <p className="mt-1 text-sm font-semibold text-muted">{t("missionPage.complete.title")}</p>
        {data.title ? <p className="text-muted">{data.title}</p> : null}
        <ul className="mt-4 space-y-2">
          <LootRow icon={Sparkles} strong>
            {data.xp > 0 ? t("missionPage.complete.xp").replace("{xp}", xpShown) : t("missionPage.complete.noXp")}
          </LootRow>
          {data.leveledUp && data.newLevel ? (
            <LootRow icon={TrendingUp}>
              {t("missionPage.complete.levelUp").replace("{level}", data.newLevel)}
            </LootRow>
          ) : data.level ? (
            <LootRow icon={TrendingUp}>
              {t("missionPage.complete.level").replace("{level}", data.level)}
            </LootRow>
          ) : null}
          {(data.achievements || []).map((slug) => (
            <LootRow key={slug} icon={Award}>
              {t("missionPage.complete.achievement").replace("{title}", t(`achievements.items.${slug}.title`))}
            </LootRow>
          ))}
          {data.streak > 0 ? (
            <LootRow icon={Flame}>
              {t("missionPage.complete.streak").replace("{n}", data.streak)}
            </LootRow>
          ) : null}
        </ul>
        <p className="mt-3 text-sm font-semibold text-text">
          <span aria-hidden="true" className="mr-2 text-warning">
            {"★".repeat(stars)}
            {"☆".repeat(MAX_STARS - stars)}
          </span>
          <span aria-label={starsText}>{starsText}</span>
        </p>
        <p className="mt-1 text-sm leading-relaxed text-muted">{t("missionPage.complete.starsHint")}</p>
        {data.suggestClass ? (
          <p className="mt-4 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-semibold text-text">
            {t("missionPage.complete.introDone")}
          </p>
        ) : null}
        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:flex-nowrap sm:justify-center">
          {data.suggestClass ? (
            <Link
              href="/class"
              data-autofocus
              className="inline-flex items-center justify-center rounded-full bg-primary px-4 py-2.5 font-medium tracking-wide whitespace-nowrap text-on-primary shadow-glow transition hover:bg-primary-dk"
            >
              {t("missionPage.complete.pickClass")}
            </Link>
          ) : null}
          {!data.suggestClass && data.next ? (
            <Link
              href={`/missions/${data.next.id}`}
              data-autofocus
              className="inline-flex items-center justify-center rounded-full bg-primary px-4 py-2.5 font-medium tracking-wide whitespace-nowrap text-on-primary shadow-glow transition hover:bg-primary-dk"
            >
              {t("missionPage.complete.next")}
            </Link>
          ) : null}
          <Button data-autofocus={data.suggestClass || data.next ? undefined : true} variant={data.suggestClass || data.next ? "secondary" : "rune"} onClick={onMap} className="justify-center !px-4 whitespace-nowrap">
            {t("missionPage.complete.toMap")}
          </Button>
          <Link
            href="/journey"
            className="inline-flex items-center justify-center rounded-full border border-primary/20 bg-primary/10 px-4 py-2.5 font-medium tracking-wide whitespace-nowrap text-primary transition hover:border-primary/40"
          >
            {t("missionPage.complete.toJourney")}
          </Link>
          <Button variant="ghost" onClick={onClose} className="justify-center !px-4 whitespace-nowrap">
            {t("missionPage.complete.stay")}
          </Button>
        </div>
      </div>
    </div>
  );
}
