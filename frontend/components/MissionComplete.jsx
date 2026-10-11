import { useId, useRef } from "react";
import Link from "next/link";
import { Star } from "lucide-react";
import Button from "./Button";
import { useDialog } from "../lib/useDialog";
import { useI18n } from "../lib/i18n";

const MAX_STARS = 3;

/**
 * Окно «миссия пройдена»: итог, звёзды и куда идти дальше. Закрывается Esc,
 * кликом по фону или кнопкой «Остаться».
 */
export default function MissionComplete({ data, onClose, onMap }) {
  const { t } = useI18n();
  const ref = useRef(null);
  const titleId = useId();
  useDialog(Boolean(data), ref, onClose);
  if (!data) return null;

  const stars = Math.max(0, Math.min(MAX_STARS, Number(data.stars) || 0));

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
        className="complete-card w-full max-w-md rounded-3xl border-2 border-card-border bg-modal-bg p-8 text-center text-modal-text shadow-[0_20px_60px_-15px_rgba(0,0,0,0.6)]"
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
          {t("missionPage.complete.title")}
        </h2>
        {data.title ? <p className="mt-1 text-muted">{data.title}</p> : null}
        <p className="mt-4 font-display text-2xl font-bold text-primary">
          {data.xp > 0
            ? t("missionPage.complete.xp").replace("{xp}", data.xp)
            : t("missionPage.complete.noXp")}
        </p>
        <p className="mt-2 text-sm leading-relaxed text-muted">{t("missionPage.complete.starsHint")}</p>
        {data.suggestClass ? (
          <p className="mt-4 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-semibold text-text">
            {t("missionPage.complete.introDone")}
          </p>
        ) : null}
        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          {data.suggestClass ? (
            <Link
              href="/class"
              data-autofocus
              className="inline-flex items-center justify-center rounded-full bg-primary px-5 py-2.5 font-medium tracking-wide text-on-primary shadow-glow transition hover:bg-primary-dk"
            >
              {t("missionPage.complete.pickClass")}
            </Link>
          ) : null}
          <Button data-autofocus={data.suggestClass ? undefined : true} variant={data.suggestClass ? "secondary" : "rune"} onClick={onMap} className="justify-center">
            {t("missionPage.complete.toMap")}
          </Button>
          <Link
            href="/journey"
            className="inline-flex items-center justify-center rounded-full border border-primary/20 bg-primary/10 px-5 py-2.5 font-medium tracking-wide text-primary transition hover:border-primary/40"
          >
            {t("missionPage.complete.toJourney")}
          </Link>
          <Button variant="ghost" onClick={onClose} className="justify-center">
            {t("missionPage.complete.stay")}
          </Button>
        </div>
      </div>
    </div>
  );
}
