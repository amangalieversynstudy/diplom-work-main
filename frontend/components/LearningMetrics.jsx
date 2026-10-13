import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, Gauge, LifeBuoy, Repeat, TrendingDown } from "lucide-react";
import { Analytics as AnalyticsAPI } from "../lib/api";
import logger from "../lib/logger";
import { useI18n } from "../lib/i18n";
import { unit } from "../lib/plural";
import { heatCellState, kpiState } from "../lib/metricsView";

const WINDOW_OPTIONS = [3, 7, 14, 30];
// Окно по умолчанию совпадает с бэкендом (ABANDON_WINDOW_DAYS) и с окном гипотез пилота.
const DEFAULT_WINDOW = 14;
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

export default function LearningMetrics() {
  const { t, language } = useI18n();
  const [days, setDays] = useState(DEFAULT_WINDOW);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

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

      <div className="grid sm:grid-cols-3 gap-4">
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
        {fill(t("analytics.metrics.windowHelp"), { n: data.meta.inactive_days })}{" "}
        {fill(t("analytics.metrics.inProgressNote"), {
          steps: kpi.steps_in_progress,
          missions: kpi.missions_in_progress,
        })}
      </p>

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
            {missions.map((mission) => (
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
                <th className="py-1 pr-3 font-bold text-right">{t("analytics.metrics.tasks.colHelp")}</th>
                <th className="py-1 font-bold">{t("analytics.metrics.tasks.colError")}</th>
              </tr>
            </thead>
            <tbody>
              {data.tasks.map((row) => (
                <tr key={row.task_id} className="border-t border-border tabular-nums">
                  <td className="py-1.5 pr-3 text-text max-w-[12rem] truncate">{row.mission_title}</td>
                  <td className="py-1.5 pr-3 text-muted">
                    {row.order} · {typeLabel(row.task_type)}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-text">{row.opened}</td>
                  <td className="py-1.5 pr-3 text-right text-text">{pct(row.solve_rate)}</td>
                  <td className="py-1.5 pr-3 text-right text-text">{num(row.mas)}</td>
                  <td className="py-1.5 pr-3 text-right text-text">{pct(row.dropout_rate)}</td>
                  <td className="py-1.5 pr-3 text-right text-muted">{pct(row.help_rate)}</td>
                  <td className="py-1.5 text-muted">{row.top_error || none}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
