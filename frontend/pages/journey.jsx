import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Compass,
  Flame,
  LifeBuoy,
  RotateCcw,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import Layout from "../components/Layout";
import { Learning } from "../lib/api";
import { useI18n } from "../lib/i18n";
import logger from "../lib/logger";

// Тон блока статуса: цвет и значок. Слова для ученика мягкие: без «риска» и процентов.
const STATUS_STYLE = {
  new: { icon: Compass, ring: "border-primary/30 bg-primary/10", tone: "text-primary" },
  great: { icon: Sparkles, ring: "border-success/30 bg-success/10", tone: "text-success" },
  steady: { icon: TrendingUp, ring: "border-primary/30 bg-primary/10", tone: "text-primary" },
  stuck: { icon: LifeBuoy, ring: "border-warning/40 bg-warning/10", tone: "text-warning" },
  away: { icon: CalendarClock, ring: "border-accent/40 bg-accent/10", tone: "text-accent" },
};

const fmt = (template, values) =>
  Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, value), template);

function Tile({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-2xl border border-border bg-panel p-4">
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 font-display text-3xl font-bold text-text tabular-nums">{value}</p>
      {hint ? <p className="mt-1 text-xs leading-snug text-muted">{hint}</p> : null}
    </div>
  );
}

function StepList({ title, empty, items, action, t }) {
  return (
    <section className="rounded-3xl border border-border bg-panel p-5">
      <h2 className="font-display text-lg font-bold text-text">{title}</h2>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item.task_id}>
              <Link
                href={`/missions/${item.mission_id}`}
                className="group flex min-h-[56px] items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3 transition-colors hover:border-primary/50"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold text-text">{item.title}</span>
                  <span className="block truncate text-xs text-muted">
                    {item.mission_title} · {fmt(t("journey.attemptsShort"), { n: item.attempts })}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-1 text-sm font-semibold text-primary">
                  {action}
                  <ArrowRight size={16} aria-hidden="true" className="transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ActivityChart({ days, t, language }) {
  const max = Math.max(1, ...days.map((d) => d.runs));
  const total = days.reduce((sum, d) => sum + d.runs, 0);
  const solved = days.reduce((sum, d) => sum + d.solved, 0);
  const weekday = new Intl.DateTimeFormat(language === "en" ? "en" : "ru", { weekday: "short" });
  const summary = fmt(t("journey.activitySummary"), { runs: total, solved });

  return (
    <section className="rounded-3xl border border-border bg-panel p-5">
      <h2 className="font-display text-lg font-bold text-text">{t("journey.activityTitle")}</h2>
      <p className="mt-1 text-sm text-muted">{summary}</p>
      <div
        role="img"
        aria-label={summary}
        className="mt-4 flex h-32 items-end gap-1.5 sm:gap-2"
      >
        {days.map((day) => {
          const height = day.runs ? Math.max(8, Math.round((day.runs / max) * 100)) : 4;
          const date = new Date(`${day.date}T12:00:00`);
          return (
            <div key={day.date} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
              {day.solved > 0 ? (
                <CheckCircle2 size={14} className="text-success" aria-hidden="true" />
              ) : (
                <span className="h-3.5" aria-hidden="true" />
              )}
              <div
                className={`w-full rounded-t-md transition-all duration-700 ${
                  day.runs ? "bg-primary" : "bg-border"
                }`}
                style={{ height: `${height}%` }}
              />
              <span className="hidden text-xs text-muted sm:block" aria-hidden="true">
                {weekday.format(date).slice(0, 2)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-muted">{t("journey.activityLegend")}</p>
    </section>
  );
}

export default function Journey() {
  const { t, language } = useI18n();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    Learning.me()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        logger.error("journey load failed", err);
        if (active) {
          setFailed(true);
          toast.error(t("journey.loadFail"));
        }
      });
    return () => {
      active = false;
    };
    // язык меняет только названия шагов, поэтому перезагружаем при его смене
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  if (!data) {
    return (
      <Layout>
        <div className="mx-auto max-w-5xl pt-16">
          {failed ? (
            <p role="alert" className="text-center text-muted">{t("journey.loadFail")}</p>
          ) : (
            <div className="space-y-4" aria-busy="true">
              <div className="h-40 animate-pulse rounded-3xl border border-border bg-panel" />
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-panel" />
                ))}
              </div>
            </div>
          )}
        </div>
      </Layout>
    );
  }

  const style = STATUS_STYLE[data.status] || STATUS_STYLE.steady;
  const StatusIcon = style.icon;
  const { summary, attempts } = data;
  const compare =
    attempts.cohort != null
      ? fmt(t("journey.cohort"), { n: attempts.cohort })
      : t("journey.cohortHidden");

  return (
    <Layout>
      <div className="mx-auto max-w-5xl space-y-6 pt-16">
        <header>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-widest text-primary">
            <Target size={16} aria-hidden="true" />
            {t("journey.badge")}
          </div>
          <h1 className="font-display text-4xl font-bold text-text md:text-5xl">{t("journey.title")}</h1>
          <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted">{t("journey.subtitle")}</p>
        </header>

        <section className={`rounded-3xl border p-6 md:p-8 ${style.ring}`} aria-live="polite">
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <span className={`grid h-14 w-14 shrink-0 place-items-center rounded-2xl border bg-bg ${style.ring} ${style.tone}`}>
                <StatusIcon size={28} aria-hidden="true" />
              </span>
              <div>
                <h2 className="font-display text-2xl font-bold text-text">
                  {t(`journey.status.${data.status}.title`)}
                </h2>
                <p className="mt-1 max-w-xl leading-relaxed text-muted">
                  {t(`journey.status.${data.status}.body`)}
                </p>
              </div>
            </div>
            {data.next ? (
              <Link
                href={`/missions/${data.next.mission_id}`}
                className="inline-flex min-h-[48px] shrink-0 items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 font-semibold text-on-primary shadow-glow transition hover:-translate-y-0.5 hover:bg-primary-dk"
              >
                {t("journey.continue")}
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            ) : (
              <p className="text-sm font-semibold text-muted">{t("journey.nothingNext")}</p>
            )}
          </div>
          {data.next ? (
            <p className="mt-4 text-sm text-muted">
              {t("journey.nextLabel")}: <span className="font-semibold text-text">{data.next.title}</span>
              {" · "}
              {data.next.mission_title}
            </p>
          ) : null}
        </section>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Tile
            icon={Compass}
            label={t("journey.tiles.missions")}
            value={`${summary.missions_done}/${summary.missions_total}`}
          />
          <Tile
            icon={CheckCircle2}
            label={t("journey.tiles.steps")}
            value={`${summary.steps_done}/${summary.steps_total}`}
          />
          <Tile
            icon={Flame}
            label={t("journey.tiles.streak")}
            value={summary.streak}
            hint={fmt(t("journey.tiles.streakBest"), { n: summary.longest_streak })}
          />
          <Tile
            icon={RotateCcw}
            label={t("journey.tiles.attempts")}
            value={attempts.mine ?? "—"}
            hint={
              attempts.mine != null
                ? `${fmt(t("journey.firstTry"), { n: attempts.first_try_share })} ${compare}`
                : t("journey.attemptsNone")
            }
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <StepList
            title={t("journey.stuckTitle")}
            empty={t("journey.stuckEmpty")}
            items={data.stuck}
            action={t("journey.tryAgain")}
            t={t}
          />
          <StepList
            title={t("journey.reviewTitle")}
            empty={t("journey.reviewEmpty")}
            items={data.review}
            action={t("journey.repeat")}
            t={t}
          />
        </div>

        <ActivityChart days={data.activity} t={t} language={language} />

        <section className="rounded-3xl border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-bold text-text">{t("journey.missionsTitle")}</h2>
          <ul className="mt-3 space-y-3">
            {data.missions.map((mission) => {
              const pct = mission.steps_total
                ? Math.round((mission.steps_done / mission.steps_total) * 100)
                : 0;
              return (
                <li key={mission.id}>
                  <Link
                    href={`/missions/${mission.id}`}
                    className="block rounded-2xl border border-border bg-surface px-4 py-3 transition-colors hover:border-primary/50"
                  >
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0 truncate font-semibold text-text">{mission.title}</span>
                      <span className="shrink-0 text-sm tabular-nums text-muted">
                        {mission.steps_done}/{mission.steps_total}
                      </span>
                    </span>
                    <span
                      className="mt-2 block h-2 overflow-hidden rounded-full bg-border"
                      role="progressbar"
                      aria-label={mission.title}
                      aria-valuemin={0}
                      aria-valuemax={mission.steps_total}
                      aria-valuenow={mission.steps_done}
                    >
                      <span
                        className={`block h-full rounded-full transition-all duration-700 ${
                          mission.completed ? "bg-success" : "bg-primary"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </Layout>
  );
}
