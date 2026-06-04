import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Button from "../components/Button";
import { Teacher as TeacherAPI, Profile as ProfileAPI } from "../lib/api";
import logger from "../lib/logger";
import { useI18n } from "../lib/i18n";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  GraduationCap,
  Lock,
  Moon,
  Users,
} from "lucide-react";

// Карточка одной сводной метрики (учеников / застряли / активны за неделю).
function StatCard({ icon: Icon, label, value, accent = "primary" }) {
  const ring = {
    primary: "text-primary bg-primary/10 border-primary/20",
    amber: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    green: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
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

// Бейдж статуса ученика: «застрял» (с причиной) либо «в норме».
function StatusBadge({ student, t }) {
  if (!student.stuck) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-xs font-semibold text-emerald-400">
        <CheckCircle2 size={13} />
        {t("teacher.status.ok")}
      </span>
    );
  }
  const isAttempts = student.stuck_reason === "many_attempts";
  const Icon = isAttempts ? AlertTriangle : Moon;
  const label = isAttempts
    ? t("teacher.status.manyAttempts")
    : t("teacher.status.inactive");
  const cls = isAttempts
    ? "border-amber-400/20 bg-amber-400/10 text-amber-400"
    : "border-rose-400/20 bg-rose-400/10 text-rose-400";
  const title = isAttempts
    ? t("teacher.attemptsHint").replace("{n}", student.max_attempts)
    : undefined;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${cls}`}
    >
      <Icon size={13} />
      {label}
    </span>
  );
}

export default function TeacherPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [allowed, setAllowed] = useState(null); // null = проверяем, false = не staff
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Сначала гейтинг: показываем кабинет только staff-аккаунтам.
        const me = await ProfileAPI.me();
        const isStaff = !!(me?.is_staff ?? me?.user?.is_staff);
        if (cancelled) return;
        if (!isStaff) {
          setAllowed(false);
          setLoading(false);
          return;
        }
        setAllowed(true);
        const res = await TeacherAPI.students();
        if (!cancelled) setData(res);
      } catch (error) {
        // 401 перехватит axios-интерсептор (редирект на /login).
        if (error?.response?.status === 403) {
          if (!cancelled) setAllowed(false);
        } else {
          logger.error("Teacher students load failed:", error);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Человекочитаемая «последняя активность».
  const lastActiveLabel = (iso) => {
    if (!iso) return t("teacher.lastActive.never");
    const ts = new Date(iso).getTime();
    if (Number.isNaN(ts)) return t("teacher.lastActive.never");
    const days = Math.floor((Date.now() - ts) / 86400000);
    if (days <= 0) return t("teacher.lastActive.today");
    if (days === 1) return t("teacher.lastActive.yesterday");
    return t("teacher.lastActive.daysAgo").replace("{n}", days);
  };

  // ── Загрузка ───────────────────────────────────────────────
  if (loading) {
    return (
      <Layout>
        <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
          <div className="h-9 w-72 bg-panel rounded-lg animate-pulse mb-3" />
          <div className="h-4 w-96 bg-panel rounded animate-pulse mb-8" />
          <div className="grid sm:grid-cols-3 gap-4 mb-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-28 bg-surface border border-border rounded-3xl animate-pulse"
              />
            ))}
          </div>
          <div className="h-64 bg-surface border border-border rounded-3xl animate-pulse" />
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
            {t("teacher.staffOnly")}
          </h1>
          <p className="text-muted mb-8">{t("teacher.staffOnlyHint")}</p>
          <Button onClick={() => router.push("/")} variant="outline">
            {t("teacher.backHome")}
          </Button>
        </div>
      </Layout>
    );
  }

  const summary = data?.summary || {};
  // Сортируем застрявших наверх, чтобы преподаватель видел их первыми;
  // внутри групп сохраняем порядок бэкенда (по XP убыванию).
  const students = [...(data?.students || [])].sort(
    (a, b) => Number(b.stuck) - Number(a.stuck)
  );

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 border border-primary/20">
            <GraduationCap size={22} className="text-primary" />
          </div>
          <h1 className="text-3xl md:text-4xl font-display font-bold text-text">
            {t("teacher.title")}
          </h1>
        </div>
        <p className="text-muted mb-8">{t("teacher.subtitle")}</p>

        {/* ── Сводка ── */}
        <div className="grid sm:grid-cols-3 gap-4 mb-6">
          <StatCard
            icon={Users}
            label={t("teacher.summary.students")}
            value={summary.total_students ?? 0}
          />
          <StatCard
            icon={AlertTriangle}
            accent="amber"
            label={t("teacher.summary.stuck")}
            value={summary.stuck_count ?? 0}
          />
          <StatCard
            icon={Clock}
            accent="green"
            label={t("teacher.summary.activeWeek")}
            value={summary.active_week ?? 0}
          />
        </div>

        {/* ── Таблица учеников ── */}
        <div className="bg-surface border border-border rounded-3xl p-4 sm:p-6 shadow-sm">
          {students.length === 0 ? (
            <p className="text-sm text-muted py-10 text-center">
              {t("teacher.empty")}
            </p>
          ) : (
            <>
              {/* Заголовок таблицы — только на md+ */}
              <div className="hidden md:grid grid-cols-[1.6fr_0.5fr_0.7fr_0.9fr_0.9fr_1fr_auto] gap-3 px-3 pb-3 text-[11px] uppercase tracking-wider text-muted font-bold border-b border-border">
                <span>{t("teacher.table.student")}</span>
                <span className="text-right">{t("teacher.table.level")}</span>
                <span className="text-right">{t("teacher.table.xp")}</span>
                <span className="text-right">{t("teacher.table.completed")}</span>
                <span className="text-right">{t("teacher.table.inProgress")}</span>
                <span className="text-right">{t("teacher.table.lastActive")}</span>
                <span className="text-right whitespace-nowrap">
                  {t("teacher.table.status")}
                </span>
              </div>

              <div className="divide-y divide-border md:divide-y-0">
                {students.map((s) => (
                  <div
                    key={s.id}
                    className="md:grid md:grid-cols-[1.6fr_0.5fr_0.7fr_0.9fr_0.9fr_1fr_auto] md:items-center gap-3 px-1 md:px-3 py-3 md:hover:bg-panel/40 rounded-xl transition-colors"
                  >
                    {/* Имя + статус (статус виден на мобиле рядом с именем) */}
                    <div className="flex items-center justify-between gap-2 min-w-0 mb-2 md:mb-0">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-text truncate">
                          {s.display_name || s.username}
                        </p>
                        {s.display_name ? (
                          <p className="text-[11px] text-muted truncate">
                            @{s.username}
                          </p>
                        ) : null}
                      </div>
                      <div className="md:hidden shrink-0">
                        <StatusBadge student={s} t={t} />
                      </div>
                    </div>

                    {/* Метрики: на мобиле — подписи слева, число справа */}
                    <div className="flex justify-between md:block md:text-right text-sm">
                      <span className="md:hidden text-muted">
                        {t("teacher.table.level")}
                      </span>
                      <span className="font-semibold text-text tabular-nums">
                        {s.level}
                      </span>
                    </div>
                    <div className="flex justify-between md:block md:text-right text-sm">
                      <span className="md:hidden text-muted">
                        {t("teacher.table.xp")}
                      </span>
                      <span className="font-semibold text-text tabular-nums">
                        {s.xp}
                      </span>
                    </div>
                    <div className="flex justify-between md:block md:text-right text-sm">
                      <span className="md:hidden text-muted">
                        {t("teacher.table.completed")}
                      </span>
                      <span className="font-semibold text-emerald-400 tabular-nums">
                        {s.completed_count}
                      </span>
                    </div>
                    <div className="flex justify-between md:block md:text-right text-sm">
                      <span className="md:hidden text-muted">
                        {t("teacher.table.inProgress")}
                      </span>
                      <span className="font-semibold text-text tabular-nums">
                        {s.in_progress_count}
                      </span>
                    </div>
                    <div className="flex justify-between md:block md:text-right text-sm mt-2 md:mt-0">
                      <span className="md:hidden text-muted">
                        {t("teacher.table.lastActive")}
                      </span>
                      <span className="text-muted tabular-nums">
                        {lastActiveLabel(s.last_active)}
                      </span>
                    </div>

                    {/* Статус на md+ — отдельной (последней) колонкой справа */}
                    <div className="hidden md:flex md:justify-end">
                      <StatusBadge student={s} t={t} />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
