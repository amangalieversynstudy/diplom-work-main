import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Button from "../components/Button";
import { Analytics as AnalyticsAPI, Profile as ProfileAPI } from "../lib/api";
import logger from "../lib/logger";
import { useI18n } from "../lib/i18n";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock,
  Flame,
  Lock,
  Repeat,
  Sparkles,
  Target,
  Users,
} from "lucide-react";

// Карточка одной метрики — крупное число + подпись + иконка.
function StatCard({ icon: Icon, label, value, sub, accent = "primary" }) {
  const ring = {
    primary: "text-primary bg-primary/10 border-primary/20",
    accent: "text-accent bg-accent/10 border-accent/20",
    green: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    blue: "text-sky-400 bg-sky-400/10 border-sky-400/20",
  }[accent];

  return (
    <div className="bg-surface border border-border rounded-3xl p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-widest font-bold text-muted mb-2">
            {label}
          </p>
          <p className="text-3xl font-display font-bold text-text leading-none tabular-nums">
            {value}
          </p>
          {sub ? <p className="text-xs text-muted mt-2">{sub}</p> : null}
        </div>
        <div
          className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${ring}`}
        >
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
}

// Горизонтальная полоса прогресса (0–100%).
function Meter({ pct, accent = "primary" }) {
  const bar = {
    primary: "bg-primary",
    accent: "bg-accent",
    green: "bg-emerald-400",
  }[accent];
  const clamped = Math.max(0, Math.min(100, Number(pct) || 0));
  return (
    <div className="h-2 w-full rounded-full bg-panel overflow-hidden border border-border">
      <div
        className={`h-full rounded-full ${bar} transition-[width] duration-500`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export default function AnalyticsPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [allowed, setAllowed] = useState(null); // null = проверяем, false = не staff
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Сначала узнаём, staff ли пользователь (гейтинг страницы).
        const me = await ProfileAPI.me();
        const isStaff = !!(me?.is_staff ?? me?.user?.is_staff);
        if (cancelled) return;
        if (!isStaff) {
          setAllowed(false);
          setLoading(false);
          return;
        }
        setAllowed(true);
        const stats = await AnalyticsAPI.get();
        if (!cancelled) setData(stats);
      } catch (error) {
        // 401 перехватит axios-интерсептор (редирект на /login).
        if (error?.response?.status === 403) {
          if (!cancelled) setAllowed(false);
        } else {
          logger.error("Analytics load failed:", error);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Загрузка ───────────────────────────────────────────────
  if (loading) {
    return (
      <Layout>
        <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
          <div className="h-9 w-72 bg-panel rounded-lg animate-pulse mb-3" />
          <div className="h-4 w-96 bg-panel rounded animate-pulse mb-8" />
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-28 bg-surface border border-border rounded-3xl animate-pulse"
              />
            ))}
          </div>
        </div>
      </Layout>
    );
  }

  // ── Не staff ───────────────────────────────────────────────
  if (allowed === false) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto pt-32 pb-16 px-4 text-center">
          <div className="grid h-16 w-16 mx-auto place-items-center rounded-2xl bg-panel border border-border mb-6">
            <Lock size={28} className="text-muted" />
          </div>
          <h1 className="text-2xl font-display font-bold text-text mb-3">
            {t("analytics.staffOnly")}
          </h1>
          <p className="text-muted mb-8">{t("analytics.staffOnlyHint")}</p>
          <Button onClick={() => router.push("/")} variant="outline">
            {t("analytics.backHome")}
          </Button>
        </div>
      </Layout>
    );
  }

  const users = data?.users || {};
  const missions = data?.missions || {};
  const streaks = data?.streaks || {};
  const hardest = data?.hardest_missions || [];
  const taskTypes = data?.task_types || [];

  const fmt = (n) => Number(n ?? 0).toLocaleString();
  const typeLabel = (key) => {
    const known = t(`analytics.taskTypes.types.${key}`);
    return known && !known.startsWith("analytics.") ? known : key;
  };

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 border border-primary/20">
            <BarChart3 size={22} className="text-primary" />
          </div>
          <h1 className="text-3xl md:text-4xl font-display font-bold text-text">
            {t("analytics.title")}
          </h1>
        </div>
        <p className="text-muted mb-8">{t("analytics.subtitle")}</p>

        {/* ── Карточки метрик ── */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            icon={CheckCircle2}
            accent="green"
            label={t("analytics.cards.completion")}
            value={`${missions.completion_rate ?? 0}%`}
            sub={`${fmt(missions.completed)} / ${fmt(missions.attempted)} ${t(
              "analytics.cards.attempted"
            )}`}
          />
          <StatCard
            icon={Repeat}
            label={t("analytics.cards.avgAttempts")}
            value={missions.avg_attempts ?? 0}
          />
          <StatCard
            icon={Clock}
            label={t("analytics.cards.avgMinutes")}
            value={`${missions.avg_minutes ?? 0} ${t("analytics.units.min")}`}
          />
          <StatCard
            icon={Target}
            accent="accent"
            label={t("analytics.cards.totalMissions")}
            value={fmt(missions.total)}
          />
          <StatCard
            icon={Users}
            accent="blue"
            label={t("analytics.cards.activeLearners")}
            value={fmt(users.active_learners)}
            sub={`${fmt(users.active_week)} ${t("analytics.cards.activeWeek")}`}
          />
          <StatCard
            icon={Flame}
            accent="accent"
            label={t("analytics.cards.activeStreaks")}
            value={fmt(streaks.active)}
            sub={`${t("analytics.cards.bestStreak")}: ${streaks.best_ever ?? 0} ${t(
              "analytics.units.days"
            )}`}
          />
          <StatCard
            icon={Activity}
            label={t("analytics.cards.totalUsers")}
            value={fmt(users.total)}
          />
          <StatCard
            icon={Sparkles}
            accent="accent"
            label={t("analytics.cards.totalXp")}
            value={fmt(data?.total_xp)}
          />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* ── Где застревают ── */}
          <div className="bg-surface border border-border rounded-3xl p-6 shadow-sm">
            <h2 className="text-lg font-bold text-text mb-1 flex items-center gap-2">
              <Target size={18} className="text-accent" />
              {t("analytics.hardest.title")}
            </h2>
            <p className="text-xs text-muted mb-5">
              {t("analytics.hardest.subtitle")}
            </p>

            {hardest.length === 0 ? (
              <p className="text-sm text-muted py-6 text-center">
                {t("analytics.hardest.empty")}
              </p>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-[1fr_auto_auto] gap-3 text-[11px] uppercase tracking-wider text-muted font-bold px-1">
                  <span>{t("analytics.hardest.colMission")}</span>
                  <span className="text-right w-16">
                    {t("analytics.hardest.colAttempts")}
                  </span>
                  <span className="text-right w-20">
                    {t("analytics.hardest.colCompletion")}
                  </span>
                </div>
                {hardest.map((m) => (
                  <div
                    key={m.mission_id}
                    className="grid grid-cols-[1fr_auto_auto] items-center gap-3 bg-panel border border-border rounded-xl px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-text font-medium truncate">
                        {m.title}
                      </p>
                      <p className="text-[11px] text-muted">
                        {m.learners} {t("analytics.units.learners")}
                      </p>
                    </div>
                    <span className="text-right w-16 text-sm font-bold text-text tabular-nums">
                      {m.avg_attempts}
                    </span>
                    <span className="text-right w-20 text-sm font-bold tabular-nums text-emerald-400">
                      {m.completion_rate}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Типы заданий ── */}
          <div className="bg-surface border border-border rounded-3xl p-6 shadow-sm">
            <h2 className="text-lg font-bold text-text mb-1 flex items-center gap-2">
              <BarChart3 size={18} className="text-primary" />
              {t("analytics.taskTypes.title")}
            </h2>
            <p className="text-xs text-muted mb-5">
              {t("analytics.taskTypes.subtitle")}
            </p>

            {taskTypes.length === 0 ? (
              <p className="text-sm text-muted py-6 text-center">
                {t("analytics.taskTypes.empty")}
              </p>
            ) : (
              <div className="space-y-4">
                {taskTypes.map((tt) => (
                  <div key={tt.task_type}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm text-text font-medium capitalize">
                        {typeLabel(tt.task_type)}
                      </span>
                      <span className="text-xs text-muted tabular-nums">
                        {tt.completion_rate}% · {fmt(tt.total)}
                      </span>
                    </div>
                    <Meter pct={tt.completion_rate} accent="primary" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
