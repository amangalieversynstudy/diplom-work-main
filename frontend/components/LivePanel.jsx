import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity,
  Bot,
  CheckCircle2,
  Flag,
  LifeBuoy,
  Lightbulb,
  Terminal,
  Trophy,
  XCircle,
} from "lucide-react";
import { Teacher as TeacherAPI } from "../lib/api";
import logger from "../lib/logger";

const POLL_MS = 10000; // совпадает с poll_seconds на сервере (game/live.py)

const fill = (template, values) =>
  Object.entries(values).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template
  );

const GOOD = "text-emerald-700 dark:text-emerald-400";
const BAD = "text-rose-700 dark:text-rose-400";
const WARN = "text-amber-800 dark:text-amber-400";
const NEUTRAL = "text-muted";

// Что показываем для каждого вида события: значок и цвет.
const KINDS = {
  code_ok: { icon: CheckCircle2, tone: GOOD },
  code_fail: { icon: XCircle, tone: BAD },
  code_run: { icon: Terminal, tone: NEUTRAL },
  quiz_ok: { icon: CheckCircle2, tone: GOOD },
  quiz_fail: { icon: XCircle, tone: BAD },
  explain_ok: { icon: CheckCircle2, tone: GOOD },
  explain_fail: { icon: XCircle, tone: WARN },
  mission_started: { icon: Flag, tone: NEUTRAL },
  mission_completed: { icon: Trophy, tone: GOOD },
  help_offered: { icon: LifeBuoy, tone: WARN },
  hint: { icon: Lightbulb, tone: NEUTRAL },
  skeleton: { icon: Lightbulb, tone: NEUTRAL },
  mentor: { icon: Bot, tone: NEUTRAL },
};

// Живая панель: кто работает прямо сейчас и что только что произошло. Опрашивает сервер каждые 10 секунд,
// пока вкладка открыта; в `since` отправляет время предыдущего ответа, по нему сервер замеряет задержку данных.
export default function LivePanel({ t, onActivity }) {
  const [live, setLive] = useState(null);
  const [fetchedAt, setFetchedAt] = useState(0);
  const [failed, setFailed] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const since = useRef(null);
  const lastSeen = useRef(undefined); // последнее действие ученика, о котором панель уже знает
  const mounted = useRef(true);
  const onActivityRef = useRef(onActivity);
  onActivityRef.current = onActivity;

  const tick = useCallback(async () => {
    try {
      const res = await TeacherAPI.live(since.current);
      if (!mounted.current) return;
      since.current = res.generated_at;
      setLive(res);
      setFetchedAt(Date.now());
      setFailed(false);
      if (lastSeen.current !== undefined && res.last_activity_at !== lastSeen.current) {
        onActivityRef.current?.(res.last_activity_at);
      }
      lastSeen.current = res.last_activity_at;
    } catch (error) {
      since.current = null; // после сбоя непонятно, что панель уже показала: замер пропускаем
      if (mounted.current) setFailed(true);
      logger.error("Live panel refresh failed:", error);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    let poll = null;
    const start = () => {
      since.current = null; // пауза была: не знаем, что панель показывала раньше
      tick();
      poll = setInterval(tick, POLL_MS);
    };
    const stop = () => {
      clearInterval(poll);
      poll = null;
    };
    const onVisibility = () => {
      if (document.hidden) {
        stop();
        setHidden(true);
      } else {
        setHidden(false);
        start();
      }
    };
    if (document.hidden) setHidden(true);
    else start();
    document.addEventListener("visibilitychange", onVisibility);
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      mounted.current = false;
      stop();
      clearInterval(clock);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [tick]);

  const agoLabel = (seconds) => {
    const s = Math.max(0, Math.round(seconds));
    if (s < 60) return fill(t("teacher.live.secondsAgo"), { n: s });
    if (s < 3600) return fill(t("teacher.live.minutesAgo"), { n: Math.floor(s / 60) });
    return fill(t("teacher.live.hoursAgo"), { n: Math.floor(s / 3600) });
  };
  const sinceFetch = Math.max(0, (now - fetchedAt) / 1000); // сколько прошло после последнего ответа

  const fresh = live?.freshness;
  const lastActivity =
    live?.last_activity_at &&
    (Date.parse(live.generated_at) - Date.parse(live.last_activity_at)) / 1000 + sinceFetch;

  return (
    <section
      aria-labelledby="live-title"
      className="bg-surface border border-border rounded-3xl p-4 sm:p-6 shadow-sm mb-6"
    >
      <h2 id="live-title" className="text-lg font-bold text-text mb-1 flex items-center gap-2">
        <Activity size={18} className="text-primary" aria-hidden="true" />
        {t("teacher.live.title")}
        {live && !failed && !hidden ? (
          <span
            className="ml-1 h-2 w-2 rounded-full bg-emerald-500 motion-safe:animate-pulse"
            aria-hidden="true"
          />
        ) : null}
      </h2>
      <p className="text-xs text-muted mb-4">{t("teacher.live.subtitle")}</p>

      {!live ? (
        <div className="h-24 rounded-2xl bg-panel motion-safe:animate-pulse" aria-hidden="true" />
      ) : (
        <>
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 mb-3">
            <p className="text-sm text-text">
              <span className="text-2xl font-display font-bold tabular-nums mr-1">{live.active_now}</span>
              {t("teacher.live.activeNow")}{" "}
              <span className="text-muted">
                {fill(t("teacher.live.activeWindow"), { m: live.active_window_minutes })}
              </span>
            </p>
            <p className="text-xs text-muted">
              {live.last_activity_at
                ? fill(t("teacher.live.lastActivity"), { ago: agoLabel(lastActivity) })
                : t("teacher.live.noActivity")}
            </p>
          </div>

          {live.events.length === 0 ? (
            <p className="text-sm text-muted py-2">{t("teacher.live.empty")}</p>
          ) : (
            <ul className="space-y-1.5">
              {live.events.map((item, index) => {
                const style = KINDS[item.kind] || KINDS.code_run;
                const Icon = style.icon;
                return (
                  <li
                    key={`${item.at}-${item.learner}-${index}`}
                    className="flex items-start gap-3 rounded-xl border border-border bg-panel px-3 py-2"
                  >
                    <Icon size={16} className={`mt-0.5 shrink-0 ${style.tone}`} aria-hidden="true" />
                    <p className="min-w-0 flex-1 text-sm text-text">
                      <Link
                        href={`/teacher/student/${item.learner_id}`}
                        className="font-semibold underline-offset-4 hover:text-primary hover:underline"
                      >
                        {item.learner}
                      </Link>{" "}
                      <span className="text-muted">{t(`teacher.live.kind.${item.kind}`)}</span>
                      {item.title ? <span className="text-muted">{`: ${item.title}`}</span> : null}
                    </p>
                    <span className="shrink-0 text-xs tabular-nums text-muted">
                      {agoLabel(item.lag_s + sinceFetch)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}

          <p className="text-xs text-muted mt-4">
            {failed
              ? t("teacher.live.error")
              : hidden
                ? t("teacher.live.paused")
                : fill(t("teacher.live.updated"), {
                    time: new Date(fetchedAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    }),
                    s: live.poll_seconds,
                  })}
          </p>
          <p className="text-xs text-muted mt-1">
            {fresh?.samples
              ? fill(t("teacher.live.delay"), {
                  mean: fresh.mean_s,
                  worst: fresh.worst_s,
                  pct: fresh.within_target_pct,
                  target: fresh.target_s,
                })
              : t("teacher.live.delayNone")}
          </p>
        </>
      )}
    </section>
  );
}
