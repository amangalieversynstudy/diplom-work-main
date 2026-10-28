import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Download, Gauge, LifeBuoy, Repeat, TrendingDown } from "lucide-react";
import { Analytics as AnalyticsAPI } from "../lib/api";
import logger from "../lib/logger";
import { useI18n } from "../lib/i18n";
import { unit } from "../lib/plural";
import { dailyTotals, heatCellState, kpiState, splitEmptyMissions } from "../lib/metricsView";

const WINDOW_OPTIONS = [3, 7, 14, 30];
// Окно по умолчанию совпадает с бэкендом (ABANDON_WINDOW_DAYS) и с окном гипотез пилота.
const DEFAULT_WINDOW = 14;
// «В зоне риска» в кабинете преподавателя: INACTIVE_LONG_DAYS в backend/game/warning.py.
const RISK_DAYS = 7;
const RED = "239, 68, 68";

const fill = (template, values) =>
  Object.entries(values).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template
  );

// Ячейка карты отсева: насыщенность красного — доля ушедших. Число дублирует
// цвет, чтобы карту можно было прочитать и без различения оттенков.
const heat = (rate) =>
  rate == null ? "transparent" : `rgba(${RED}, ${0.12 + 0.68 * (rate / 100)})`;

function Panel({ icon: Icon, title, subtitle, children, className = "" }) {
  return (
    <section
      className={`bg-surface border border-border rounded-3xl p-6 shadow-sm ${className}`}
    >
      <h2 className="text-lg font-bold text-text mb-1 flex items-center gap-2">
        {Icon ? <Icon size={18} className="text-primary" /> : null}
        {title}
      </h2>
      {subtitle ? <p className="text-xs text-muted mb-5">{subtitle}</p> : null}
      {children}
    </section>
  );
}

function Kpi({ label, value, hint }) {
  return (
    <div className="bg-surface border border-border rounded-3xl p-5 shadow-sm">
      <p className="text-xs uppercase tracking-widest font-bold text-muted mb-2">
        {label}
      </p>
      <p className={`${String(value).length > 8 ? "text-xl" : "text-3xl"} font-display font-bold text-text leading-none tabular-nums`}>
        {value}
      </p>
      <p className="text-xs text-muted mt-2">{hint}</p>
    </div>
  );
}

// График класса по дням: столбики это ученики, которые что-то делали, линия это решённые шаги.
// Рисуем SVG сами (без библиотеки): два ряда, подписи по краям, под графиком текстовые итоги.
function DailyChart({ daily, t }) {
  const totals = dailyTotals(daily);
  const W = 640;
  const H = 180;
  const pad = { top: 14, right: 12, bottom: 26, left: 30 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const peak = Math.max(totals.peak, 1);
  const maxSolved = Math.max(totals.maxSolved, 1);
  const step = innerW / Math.max(daily.length, 1);
  const x = (i) => pad.left + step * i + step / 2;
  const barH = (value) => (value / peak) * innerH;
  const lineY = (value) => pad.top + innerH - (value / maxSolved) * innerH;
  const line = daily.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${lineY(d.solved).toFixed(1)}`).join(" ");
  const dayLabel = (iso) => iso.slice(8, 10) + "." + iso.slice(5, 7);
  const label = (d) =>
    fill(t("analytics.metrics.daily.point"), { date: dayLabel(d.date), active: d.active, solved: d.solved, runs: d.runs });

  if (totals.empty) {
    return (
      <p className="text-sm text-muted py-4 text-center">
        {fill(t("analytics.metrics.daily.empty"), { n: totals.days })}
      </p>
    );
  }
  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={fill(t("analytics.metrics.daily.total"), { n: totals.days, steps: totals.solved, peak: totals.peak })}
        className="w-full h-auto"
      >
        {[0, 0.5, 1].map((share) => (
          <g key={share}>
            <line
              x1={pad.left}
              x2={W - pad.right}
              y1={pad.top + innerH * (1 - share)}
              y2={pad.top + innerH * (1 - share)}
              stroke="currentColor"
              className="text-border"
              strokeWidth="1"
            />
            <text
              x={pad.left - 6}
              y={pad.top + innerH * (1 - share) + 3}
              textAnchor="end"
              fontSize="10"
              className="fill-current text-muted"
            >
              {Math.round(peak * share)}
            </text>
          </g>
        ))}
        {daily.map((d, i) => (
          <g key={d.date}>
            <title>{label(d)}</title>
            <rect
              x={x(i) - step * 0.3}
              y={pad.top + innerH - barH(d.active)}
              width={step * 0.6}
              height={Math.max(barH(d.active), d.active > 0 ? 2 : 0)}
              rx="3"
              className="fill-current text-primary"
              opacity="0.75"
            />
            {i % 2 === 0 || daily.length < 8 ? (
              <text x={x(i)} y={H - 8} textAnchor="middle" fontSize="10" className="fill-current text-muted">
                {dayLabel(d.date)}
              </text>
            ) : null}
          </g>
        ))}
        <path d={line} fill="none" stroke="currentColor" className="text-amber-600" strokeWidth="2" strokeLinejoin="round" />
        {daily.map((d, i) => (
          <circle key={d.date} cx={x(i)} cy={lineY(d.solved)} r="2.5" className="fill-current text-amber-600" />
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-primary opacity-75" />
          {t("analytics.metrics.daily.active")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-0.5 w-4 bg-amber-600" />
          {t("analytics.metrics.daily.solved")} ({fill(t("analytics.metrics.daily.scale"), { max: totals.maxSolved })})
        </span>
      </div>
      <p className="text-xs text-muted mt-1">
        {fill(t("analytics.metrics.daily.total"), { n: totals.days, steps: totals.solved, peak: totals.peak })}
      </p>
    </div>
  );
}

export default function LearningMetrics() {
  const { t, language } = useI18n();
  const [days, setDays] = useState(DEFAULT_WINDOW);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [showEmpty, setShowEmpty] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    AnalyticsAPI.metrics({ inactive_days: days })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((error) => {
        logger.error("Learning metrics load failed:", error);
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  const missions = useMemo(() => {
    const groups = new Map();
    (data?.tasks || []).forEach((row) => {
      if (!groups.has(row.mission_id)) {
        groups.set(row.mission_id, {
          id: row.mission_id,
          title: row.mission_title,
          steps: [],
        });
      }
      groups.get(row.mission_id).steps.push(row);
    });
    return [...groups.values()];
  }, [data]);

  const { shown: shownMissions, hidden: emptyMissions } = useMemo(() => splitEmptyMissions(missions), [missions]);
  const visibleMissions = showEmpty ? missions : shownMissions;
  const visibleIds = new Set(visibleMissions.map((mission) => mission.id));

  const downloadCsv = useCallback(async () => {
    try {
      const blob = await AnalyticsAPI.metricsCsv({ inactive_days: days });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "learning_metrics.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      logger.error("Metrics export failed:", error);
    }
  }, [days]);

  const none = t("analytics.metrics.noValue");
  const solveTime = (sec) => {
    const s = Math.max(0, Math.round(sec));
    const m = Math.floor(s / 60);
    const secU = t("analytics.metrics.tasks.secUnit");
    return m > 0 ? `${m} ${t("analytics.metrics.tasks.minUnit")} ${s % 60} ${secU}` : `${s} ${secU}`;
  };
  const pct = (value) => (value == null ? none : `${value}%`);
  const num = (value) => (value == null ? none : value);
  // процент по малой выборке не показываем: «мало данных (n=…)» вместо числа
  const kpiValue = (value, n) => {
    const s = kpiState(n, data.meta.min_sample);
    return value != null && s.few ? fill(t("analytics.metrics.kpi.few"), { n: s.n }) : pct(value);
  };
  const typeLabel = (key) => t(`analytics.taskTypes.types.${key}`);
  const helpLabel = (key) => t(`analytics.metrics.help.${key}`);

  if (failed) {
    return (
      <p role="alert" className="text-sm text-muted py-6">
        {t("analytics.metrics.loadFailed")}
      </p>
    );
  }
  if (!data) {
    return <div className="h-40 bg-surface border border-border rounded-3xl animate-pulse" />;
  }

  const { kpi, funnel, failure_curve: curve, help_effect: help } = data;
  const threshold = data.critical_threshold;
  const critical = data.critical_point;
  const share = data.meta.critical_share;
  // Оценка и нижняя граница интервала — раздельно; при нехватке данных вывода нет.
  const thresholdText =
    data.threshold_status === "found" && critical
      ? `${fill(t("analytics.metrics.threshold.found"), {
          n: critical.failures,
          est: critical.dropout_rate,
          lo: critical.ci_low,
          hi: critical.ci_high,
          learners: critical.learners,
          pairs: critical.known,
        })} ${
          critical.confirmed
            ? fill(t("analytics.metrics.threshold.confirmed"), { share })
            : fill(t("analytics.metrics.threshold.notConfirmed"), { lo: critical.ci_low, share })
        }`
      : data.threshold_status === "too_few"
      ? fill(t("analytics.metrics.threshold.tooFewAll"), {
          pairs: data.meta.min_curve_pairs,
          learners: data.meta.min_curve_learners,
        })
      : fill(t("analytics.metrics.threshold.none"), { share });
  const empty = data.meta.learners === 0;

  const emptyToggle = emptyMissions.length ? (
    <div className="flex flex-wrap items-center gap-3 pt-2 text-xs text-muted">
      {!showEmpty ? <span>{fill(t("analytics.metrics.emptyMissions.note"), { n: emptyMissions.length })}</span> : null}
      <button
        type="button"
        onClick={() => setShowEmpty((value) => !value)}
        aria-expanded={showEmpty}
        className="rounded-lg border border-border px-3 py-1.5 font-medium text-text hover:border-primary"
      >
        {showEmpty
          ? t("analytics.metrics.emptyMissions.hide")
          : fill(t("analytics.metrics.emptyMissions.show"), { n: emptyMissions.length })}
      </button>
    </div>
  ) : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-display font-bold text-text">
            {t("analytics.metrics.title")}
          </h2>
          <p className="text-muted text-sm mt-1 max-w-2xl">
            {t("analytics.metrics.subtitle")}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted flex flex-col gap-1">
            {t("analytics.metrics.windowLabel")}
            <select
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="bg-panel border border-border rounded-xl px-3 py-2 text-sm text-text"
            >
              {WINDOW_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option} {t("analytics.units.days")}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={downloadCsv}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-panel px-4 py-2 text-sm font-medium text-text hover:border-primary"
          >
            <Download size={16} aria-hidden="true" />
            {t("analytics.metrics.exportCsv")}
          </button>
        </div>
      </div>

      {empty ? (
        <p className="text-sm text-muted py-6 text-center">
          {t("analytics.metrics.empty")}
        </p>
      ) : null}

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi
          label={t("analytics.metrics.kpi.performance")}
          value={num(kpi.performance_score)}
          hint={t("analytics.metrics.kpi.performanceHint")}
        />
        <Kpi
          label={t("analytics.metrics.kpi.mcr")}
          value={kpiValue(kpi.mission_completion_rate, kpi.missions_started - kpi.missions_in_progress)}
          hint={t("analytics.metrics.kpi.mcrHint")}
        />
        <Kpi
          label={t("analytics.metrics.kpi.mas")}
          value={num(kpi.mean_attempts_to_success)}
          hint={t("analytics.metrics.kpi.masHint")}
        />
        <Kpi
          label={t("analytics.metrics.kpi.dropout")}
          value={kpiValue(kpi.task_dropout_rate, kpi.steps_known)}
          hint={t("analytics.metrics.kpi.dropoutHint")}
        />
      </div>
      <p className="text-xs text-muted">
        {data.meta.learners} {unit(t, language, "student", data.meta.learners)} {t("analytics.metrics.inSample")}
      </p>
      <p className="text-xs text-muted -mt-3">
        {fill(t("analytics.metrics.riskVsGone"), { risk: data.meta.risk_days ?? RISK_DAYS, gone: DEFAULT_WINDOW })}
      </p>
      <p className="text-xs text-muted -mt-3">
        {fill(t("analytics.metrics.windowHelp"), { n: data.meta.inactive_days })}{" "}
        {fill(t("analytics.metrics.inProgressNote"), {
          steps: kpi.steps_in_progress,
          missions: kpi.missions_in_progress,
        })}
      </p>

      <Panel
        icon={Activity}
        title={t("analytics.metrics.daily.title")}
        subtitle={fill(t("analytics.metrics.daily.subtitle"), { n: data.daily.length })}
      >
        <DailyChart daily={data.daily} t={t} />
      </Panel>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel
          icon={Gauge}
          title={t("analytics.metrics.funnel.title")}
          subtitle={t("analytics.metrics.funnel.subtitle")}
        >
          <div className="space-y-3">
            {funnel.map((row) => (
              <div
                key={row.task_type}
                className="bg-panel border border-border rounded-xl px-4 py-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-medium text-text">
                    {typeLabel(row.task_type)}
                  </span>
                  <span className="text-xs text-muted tabular-nums">
                    {row.steps} {unit(t, language, "step", row.steps)}
                  </span>
                </div>
                <p className="text-xs text-muted mt-1 tabular-nums">
                  {t("analytics.metrics.funnel.opened")} {row.opened} ·{" "}
                  {t("analytics.metrics.funnel.solved")} {row.solved} ·{" "}
                  {t("analytics.metrics.funnel.dropped")} {row.dropped} (
                  {pct(row.dropout_rate)})
                  {row.mas != null
                    ? ` · ${t("analytics.metrics.funnel.mas")} ${row.mas}`
                    : ""}
                </p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          icon={TrendingDown}
          title={t("analytics.metrics.threshold.title")}
          subtitle={t("analytics.metrics.threshold.subtitle")}
        >
          <p
            className={`text-sm mb-4 rounded-xl border px-3 py-2 ${
              threshold
                ? "border-red-400/40 bg-red-400/10 text-text"
                : "border-border bg-panel text-muted"
            }`}
          >
            {thresholdText}
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted text-left">
                <th className="py-1 font-bold">{t("analytics.metrics.threshold.colFailures")}</th>
                <th className="py-1 font-bold text-right">{t("analytics.metrics.threshold.colReached")}</th>
                <th className="py-1 font-bold text-right">{t("analytics.metrics.threshold.colDropout")}</th>
              </tr>
            </thead>
            <tbody>
              {curve.map((point) => (
                <tr key={point.failures} className="border-t border-border tabular-nums">
                  <td className="py-1.5 text-text">{point.failures}</td>
                  <td className="py-1.5 text-right text-muted">
                    {point.reached}
                    {point.reached > 0 ? ` (${point.known})` : ""}
                  </td>
                  <td className="py-1.5 text-right text-text">
                    {point.reached === 0
                      ? none
                      : !point.enough
                      ? t("analytics.metrics.threshold.tooFew")
                      : `${pct(point.dropout_rate)} (${point.ci_low}–${point.ci_high})`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <Panel
        icon={TrendingDown}
        title={t("analytics.metrics.heatmap.title")}
        subtitle={t("analytics.metrics.heatmap.subtitle")}
      >
        {missions.length === 0 ? (
          <p className="text-sm text-muted py-4 text-center">
            {t("analytics.metrics.heatmap.noData")}
          </p>
        ) : (
          <div className="space-y-2">
            {visibleMissions.map((mission) => (
              <div key={mission.id} className="flex items-center gap-3">
                <p className="w-40 shrink-0 truncate text-sm text-text" title={mission.title}>
                  {mission.title}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {mission.steps.map((step) => {
                    const cell = heatCellState(step, data.meta.min_sample);
                    const label = fill(
                      t(cell.state === "few" ? "analytics.metrics.heatmap.cellFew" : "analytics.metrics.heatmap.cell"),
                      {
                        order: step.order,
                        type: typeLabel(step.task_type),
                        opened: step.opened,
                        dropped: step.dropped,
                        known: step.known,
                        min: data.meta.min_sample,
                        rate: step.dropout_rate ?? 0,
                      }
                    );
                    return (
                      <div
                        key={step.task_id}
                        role="img"
                        aria-label={label}
                        title={label}
                        style={{
                          backgroundColor:
                            cell.state === "few" ? "rgba(148, 163, 184, 0.18)" : heat(cell.rate),
                        }}
                        className={`grid h-9 min-w-[2.75rem] place-items-center rounded-lg border border-border px-1 text-xs tabular-nums ${
                          cell.state === "few" ? "font-medium text-muted" : "font-bold text-text"
                        }`}
                      >
                        {cell.text}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
            <div className="flex items-center gap-2 pt-2 text-xs text-muted">
              <span>{t("analytics.metrics.heatmap.legendLow")}</span>
              <span
                aria-hidden="true"
                className="h-2 w-28 rounded-full"
                style={{
                  background: `linear-gradient(90deg, rgba(${RED}, 0.12), rgba(${RED}, 0.8))`,
                }}
              />
              <span>{t("analytics.metrics.heatmap.legendHigh")}</span>
              <span
                aria-hidden="true"
                className="ml-3 h-3 w-5 rounded border border-border"
                style={{ backgroundColor: "rgba(148, 163, 184, 0.18)" }}
              />
              <span>{fill(t("analytics.metrics.heatmap.legendFew"), { min: data.meta.min_sample })}</span>
            </div>
            {emptyToggle}
          </div>
        )}
      </Panel>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel
          icon={LifeBuoy}
          title={t("analytics.metrics.help.title")}
          subtitle={t("analytics.metrics.help.subtitle")}
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted text-left">
                <th className="py-1 font-bold" />
                <th className="py-1 font-bold text-right">{t("analytics.metrics.help.pairs")}</th>
                <th className="py-1 font-bold text-right">{t("analytics.metrics.help.solveRate")}</th>
                <th className="py-1 font-bold text-right">{t("analytics.metrics.help.mas")}</th>
                <th className="py-1 font-bold text-right">{t("analytics.metrics.help.dropout")}</th>
              </tr>
            </thead>
            <tbody>
              {help.map((row) => (
                <tr key={row.group} className="border-t border-border tabular-nums">
                  <td className="py-1.5 text-text">
                    {helpLabel(row.group)}
                    {row.rescued ? (
                      <span className="block text-xs text-muted">
                        {fill(t("analytics.metrics.help.rescued"), { n: row.rescued })}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-1.5 text-right text-muted">{row.pairs}</td>
                  <td className="py-1.5 text-right text-text">{pct(row.solve_rate)}</td>
                  <td className="py-1.5 text-right text-text">{num(row.mas)}</td>
                  <td className="py-1.5 text-right text-text">{pct(row.dropout_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-muted mt-4">{t("analytics.metrics.help.caveat")}</p>
        </Panel>

        <Panel
          icon={Repeat}
          title={t("analytics.metrics.errors.title")}
          subtitle={t("analytics.metrics.errors.subtitle")}
        >
          {data.top_errors.length === 0 ? (
            <p className="text-sm text-muted py-4 text-center">
              {t("analytics.metrics.errors.empty")}
            </p>
          ) : (
            <ul className="space-y-2">
              {data.top_errors.map((row) => (
                <li
                  key={row.error_type}
                  className="flex items-center justify-between gap-3 bg-panel border border-border rounded-xl px-3 py-2"
                >
                  <code className="text-sm text-text">{row.error_type}</code>
                  <span className="text-xs text-muted tabular-nums">
                    {row.runs} {unit(t, language, "run", row.runs)} · {row.learners}{" "}
                    {unit(t, language, "student", row.learners)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {data.performance ? (
        <Panel
          icon={Gauge}
          title={t("analytics.metrics.performance.title")}
          subtitle={t("analytics.metrics.performance.subtitle")}
        >
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-panel border border-border rounded-xl px-4 py-3">
              <p className="text-xs text-muted">{t("analytics.metrics.performance.mean")}</p>
              <p className="text-xl font-display font-bold text-text tabular-nums mt-0.5">
                {num(data.performance.mean_score)}
              </p>
              {data.performance.median_score != null ? (
                <p className="text-xs text-muted mt-0.5">
                  {fill(t("analytics.metrics.performance.median"), { n: data.performance.median_score })}
                </p>
              ) : null}
            </div>
            <div className="bg-panel border border-border rounded-xl px-4 py-3">
              <p className="text-xs text-muted">{t("analytics.metrics.performance.stepsShare")}</p>
              <p className="text-xl font-display font-bold text-text tabular-nums mt-0.5">
                {pct(data.performance.steps_share)}
              </p>
            </div>
            <div className="bg-panel border border-border rounded-xl px-4 py-3">
              <p className="text-xs text-muted">{t("analytics.metrics.performance.starsShare")}</p>
              <p className="text-xl font-display font-bold text-text tabular-nums mt-0.5">
                {pct(data.performance.stars_share)}
              </p>
            </div>
            <div className="bg-panel border border-border rounded-xl px-4 py-3">
              <p className="text-xs text-muted">{t("analytics.metrics.performance.explainShare")}</p>
              <p className="text-xl font-display font-bold text-text tabular-nums mt-0.5">
                {data.performance.explain_total
                  ? pct(data.performance.explain_share)
                  : t("analytics.metrics.performance.noExplain")}
              </p>
            </div>
          </div>
          {data.performance.tiers ? (
            <p className="text-xs text-muted mt-3">
              {fill(t("analytics.metrics.performance.tiers"), {
                high: data.performance.tiers.high ?? 0,
                medium: data.performance.tiers.medium ?? 0,
                low: data.performance.tiers.low ?? 0,
              })}
            </p>
          ) : null}
        </Panel>
      ) : null}

      {data.behavioral_patterns && Array.isArray(data.behavioral_patterns.profiles) ? (
        <Panel
          icon={Activity}
          title={t("analytics.metrics.patterns.title")}
          subtitle={t("analytics.metrics.patterns.subtitle")}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-muted text-left">
                  <th className="py-1 pr-3 font-bold">{t("analytics.metrics.patterns.colProfile")}</th>
                  <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.patterns.colLearners")}</th>
                  <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.patterns.colShare")}</th>
                  <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.patterns.colPerformance")}</th>
                  <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.patterns.colAttempts")}</th>
                  <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.patterns.colHelp")}</th>
                  <th className="py-1 font-bold text-right">{t("analytics.metrics.patterns.colAway")}</th>
                </tr>
              </thead>
              <tbody>
                {data.behavioral_patterns.profiles.map((row) => (
                  <tr key={row.code} className="border-t border-border tabular-nums">
                    <td className="py-2 pr-3 text-text">
                      <span className="font-medium">
                        {t(`analytics.metrics.patterns.names.${row.code}`)}
                      </span>
                      <span className="block text-xs text-muted">
                        {t(`analytics.metrics.patterns.descriptions.${row.code}`)}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right text-text">{row.count}</td>
                    <td className="py-2 pr-3 text-right text-muted">
                      {row.share != null ? `${Math.round(row.share * 100)}%` : t("analytics.metrics.noValue")}
                    </td>
                    <td className="py-2 pr-3 text-right text-text">{num(row.mean_performance)}</td>
                    <td className="py-2 pr-3 text-right text-text">{num(row.mean_attempts)}</td>
                    <td className="py-2 pr-3 text-right text-text">
                      {row.mean_help_rate != null ? `${Math.round(row.mean_help_rate * 100)}%` : t("analytics.metrics.noValue")}
                    </td>
                    <td className="py-2 text-right text-text">{num(row.mean_away_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.behavioral_patterns.insufficient_data_count > 0 ? (
            <p className="text-xs text-muted mt-3">
              {fill(t("analytics.metrics.patterns.insufficientNote"), {
                n: data.behavioral_patterns.insufficient_data_count,
              })}
            </p>
          ) : null}
        </Panel>
      ) : null}

      <Panel title={t("analytics.metrics.tasks.title")}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted text-left">
                <th className="py-1 pr-3 font-bold">{t("analytics.metrics.tasks.colMission")}</th>
                <th className="py-1 pr-3 font-bold">{t("analytics.metrics.tasks.colStep")}</th>
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colOpened")}</th>
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colSolved")}</th>
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colMas")}</th>
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colDropout")}</th>
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colTime")}</th>
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colHelp")}</th>
                <th className="py-1 font-bold">{t("analytics.metrics.tasks.colError")}</th>
              </tr>
            </thead>
            <tbody>
              {data.tasks
                .filter((row) => visibleIds.has(row.mission_id))
                .map((row) => (
                <tr key={row.task_id} className="border-t border-border tabular-nums">
                  <td className="py-1.5 pr-3 text-text max-w-[12rem] truncate">{row.mission_title}</td>
                  <td className="py-1.5 pr-3 text-muted">
                    {row.order} · {typeLabel(row.task_type)}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-text">{row.opened}</td>
                  <td className="py-1.5 pr-3 text-right text-text">{pct(row.solve_rate)}</td>
                  <td className="py-1.5 pr-3 text-right text-text">{num(row.mas)}</td>
                  <td className="py-1.5 pr-3 text-right text-text">{pct(row.dropout_rate)}</td>
                  <td
                    className="py-1.5 pr-3 text-right text-text"
                    title={row.median_solve_n ? t("analytics.metrics.tasks.timeTitle").replace("{n}", row.median_solve_n) : undefined}
                  >
                    {row.median_solve_s == null ? none : solveTime(row.median_solve_s)}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-muted">{pct(row.help_rate)}</td>
                  <td className="py-1.5 text-muted">{row.top_error || none}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {emptyToggle}
      </Panel>
    </div>
  );
}
