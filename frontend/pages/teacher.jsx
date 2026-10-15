import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Button from "../components/Button";
import LivePanel from "../components/LivePanel";
import UsabilityPanel from "../components/UsabilityPanel";
import {
  Analytics as AnalyticsAPI,
  Teacher as TeacherAPI,
  Profile as ProfileAPI,
} from "../lib/api";
import logger from "../lib/logger";
import { filterAndSortStudents, warningEmptyState } from "../lib/students";
import { useI18n } from "../lib/i18n";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  GraduationCap,
  LifeBuoy,
  Lock,
  Moon,
  ShieldCheck,
  Users,
} from "lucide-react";

// Карточка одной сводной метрики (учеников / застряли / активны за неделю).
function StatCard({ icon: Icon, label, value, accent = "primary" }) {
  const ring = {
    primary: "text-primary bg-primary/10 border-primary/20",
    amber: "text-amber-800 dark:text-amber-400 bg-amber-400/10 border-amber-400/20",
    green: "text-emerald-700 dark:text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
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

// Бейдж статуса ученика. Тот же уровень и те же слова, что в списке «Кому нужна помощь сейчас»
// (Срочно / Внимание / В норме): оба экрана считает система раннего предупреждения.
function StatusBadge({ student, t }) {
  const level = student.warning_level || (student.stuck ? "medium" : "ok");
  if (level === "ok") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 size={13} />
        {t("teacher.status.ok")}
      </span>
    );
  }
  const Icon = student.stuck_reason === "inactive" ? Moon : AlertTriangle;
  const cls =
    level === "high"
      ? "border-rose-400/30 bg-rose-400/10 text-rose-700 dark:text-rose-400"
      : "border-amber-400/30 bg-amber-400/10 text-amber-800 dark:text-amber-400";
  const title =
    student.stuck_reason === "many_attempts"
      ? t("teacher.attemptsHint").replace("{n}", student.max_attempts)
      : undefined;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${cls}`}
    >
      <Icon size={13} />
      {t(`teacher.warning.${level}`)}
    </span>
  );
}

// Вся строка ведёт на страницу ученика: ссылка растянута на строку, поэтому клик в любое место
// открывает ученика, а для клавиатуры и скринридера это по-прежнему одна ссылка.
const ROW_LINK = "after:absolute after:inset-0 after:content-['']";
const ROW_HOVER =
  "relative transition-colors hover:border-primary/50 hover:bg-surface focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/30";

const fill = (template, values) =>
  Object.entries(values).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template
  );

// Список раннего предупреждения: кому нужна помощь и по какой причине.
function EarlyWarningPanel({ warning, t }) {
  const students = warning?.students || [];
  const rules = warning?.rules;
  const emptyState = warningEmptyState(warning?.summary);
  const reasonText = (reason) => {
    if (reason.code === "stuck_task") {
      return fill(t("teacher.warning.reasonStuck"), {
        n: reason.failures,
        task: reason.task_title || `${t("teacher.warning.step")} #${reason.task_id}`,
        mission: reason.mission_title,
      });
    }
    if (reason.code === "model_risk") {
      return t("teacher.warning.reasonModel");
    }
    return reason.days == null
      ? t("teacher.warning.reasonNeverSeen")
      : fill(t("teacher.warning.reasonInactive"), { n: reason.days });
  };

  return (
    <section
      aria-labelledby="early-warning-title"
      className="bg-surface border border-border rounded-3xl p-4 sm:p-6 shadow-sm mb-6"
    >
      <h2
        id="early-warning-title"
        className="text-lg font-bold text-text mb-1 flex items-center gap-2"
      >
        <LifeBuoy size={18} className="text-amber-700 dark:text-amber-400" />
        {t("teacher.warning.title")}
      </h2>
      <p className="text-xs text-muted mb-4">{t("teacher.warning.subtitle")}</p>

      {students.length === 0 ? (
        <p className="text-sm text-muted py-4 text-center">
          {emptyState === "clear"
            ? fill(t("teacher.warning.empty"), { n: warning?.summary?.total })
            : t(`teacher.warning.${emptyState}`)}
        </p>
      ) : (
        <ul className="space-y-2">
          {students.map((s) => (
            <li
              key={s.id}
              className={`${ROW_HOVER} flex flex-wrap items-start gap-3 bg-panel border border-border rounded-xl px-3 py-2.5`}
            >
              <span
                className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${
                  s.level === "high"
                    ? "border-rose-400/30 bg-rose-400/10 text-rose-700 dark:text-rose-400"
                    : "border-amber-400/30 bg-amber-400/10 text-amber-800 dark:text-amber-400"
                }`}
              >
                {t(`teacher.warning.${s.level}`)}
              </span>
              <div className="min-w-0 flex-1">
                <Link
                  href={`/teacher/student/${s.id}`}
                  className={`${ROW_LINK} text-sm font-semibold text-text underline-offset-4 hover:text-primary hover:underline truncate block py-1.5 -my-1.5 focus:outline-none`}
                >
                  {s.display_name || s.username}
                </Link>
                <ul className="text-xs text-muted space-y-0.5 mt-0.5">
                  {s.reasons.map((reason) => (
                    <li key={reason.code}>{reasonText(reason)}</li>
                  ))}
                </ul>
              </div>
              <ChevronRight size={18} className="shrink-0 self-center text-muted" aria-hidden="true" />
            </li>
          ))}
        </ul>
      )}
      {rules ? (
        <p className="text-xs text-muted mt-4">
          {fill(t("teacher.warning.rules"), {
            n: rules.stuck_failures,
            days: rules.inactive_long_days,
          })}
        </p>
      ) : null}
    </section>
  );
}

// С кого начать разговор о решениях. Признаки приходят из браузера и могут быть неполными, поэтому
// здесь только «где посмотреть», а подробности и оговорки на странице ученика.
function AuthorshipWatchPanel({ overview, t }) {
  const students = overview?.students;
  if (!students) return null; // не загрузилось: кабинет остаётся как есть
  return (
    <section
      aria-labelledby="authorship-watch-title"
      className="bg-surface border border-border rounded-3xl p-4 sm:p-6 shadow-sm mb-6"
    >
      <h2 id="authorship-watch-title" className="text-lg font-bold text-text mb-1 flex items-center gap-2">
        <ShieldCheck size={18} className="text-primary" aria-hidden="true" />
        {t("teacher.authorshipWatch.title")}
      </h2>
      <p className="text-xs text-muted mb-4">{t("teacher.authorshipWatch.subtitle")}</p>
      {students.length === 0 ? (
        <p className="text-sm text-muted">{t("teacher.authorshipWatch.empty")}</p>
      ) : (
        <ul className="space-y-2">
          {students.map((s) => (
            <li
              key={s.id}
              className={`${ROW_HOVER} flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-border bg-panel px-4 py-2`}
            >
              <Link
                href={`/teacher/student/${s.id}`}
                className={`${ROW_LINK} block py-1.5 -my-1.5 text-sm font-semibold text-text underline-offset-4 hover:text-primary hover:underline focus:outline-none`}
              >
                {s.username}
              </Link>
              <span className="flex items-center gap-2 text-xs text-muted">
                {fill(t("teacher.authorshipWatch.row"), { flagged: s.flagged, solved: s.solved })}
                <ChevronRight size={16} aria-hidden="true" />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function TeacherPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [allowed, setAllowed] = useState(null); // null = проверяем, false = не staff
  const [data, setData] = useState(null);
  const [warning, setWarning] = useState(null);
  const [authorship, setAuthorship] = useState(null);
  const [loading, setLoading] = useState(true);
  const refreshedAt = useRef(0);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState(null);
  const [direction, setDirection] = useState("desc");

  // Новая активность учеников: обновляем списки сами, но не чаще раза в 30 секунд.
  const refreshLists = useCallback(async () => {
    if (Date.now() - refreshedAt.current < 30000) return;
    refreshedAt.current = Date.now();
    try {
      const [res, warned, overview] = await Promise.all([
        TeacherAPI.students(),
        AnalyticsAPI.earlyWarning(),
        TeacherAPI.authorshipOverview(),
      ]);
      setData(res);
      setWarning(warned);
      setAuthorship(overview);
    } catch (error) {
      logger.error("Teacher lists refresh failed:", error);
    }
  }, []);

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
        const [res, warned] = await Promise.all([
          TeacherAPI.students(),
          AnalyticsAPI.earlyWarning(),
        ]);
        if (!cancelled) {
          setData(res);
          setWarning(warned);
          refreshedAt.current = Date.now();
        }
        TeacherAPI.authorshipOverview()
          .then((overview) => {
            if (!cancelled) setAuthorship(overview);
          })
          .catch((error) => logger.error("Authorship overview load failed:", error));
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
  const allStudents = data?.students || [];
  const students = filterAndSortStudents(allStudents, { query, sortKey, direction });
  // Клик по заголовку: сначала по убыванию (имя: по алфавиту), второй клик меняет направление,
  // третий возвращает прежний порядок.
  const toggleSort = (key) => {
    if (sortKey !== key) {
      setSortKey(key);
      setDirection(key === "name" ? "asc" : "desc");
    } else if (direction === (key === "name" ? "asc" : "desc")) {
      setDirection(key === "name" ? "desc" : "asc");
    } else {
      setSortKey(null);
    }
  };
  const sortHead = (key, label, extra = "") => (
    <button
      type="button"
      onClick={() => toggleSort(key)}
      aria-label={`${t("teacher.search.sortBy")}: ${label}`}
      className={`inline-flex min-h-[32px] items-center gap-1 uppercase tracking-wider font-bold hover:text-text ${extra}`}
    >
      {label}
      <span aria-hidden="true">{sortKey === key ? (direction === "asc" ? "▲" : "▼") : ""}</span>
    </button>
  );
  const ariaSort = (key) => (sortKey === key ? (direction === "asc" ? "ascending" : "descending") : undefined);

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

        <LivePanel t={t} onActivity={refreshLists} />
        <EarlyWarningPanel warning={warning} t={t} />
        <AuthorshipWatchPanel overview={authorship} t={t} />

        {/* ── Таблица учеников ── */}
        <div className="bg-surface border border-border rounded-3xl p-4 sm:p-6 shadow-sm">
          {allStudents.length === 0 ? (
            <p className="text-sm text-muted py-10 text-center">
              {t("teacher.empty")}
            </p>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t("teacher.search.placeholder")}
                  aria-label={t("teacher.search.label")}
                  className="min-h-[44px] w-full min-w-[14rem] flex-1 rounded-xl border border-border bg-panel px-4 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none sm:max-w-sm"
                />
                <p className="text-xs text-muted" role="status" aria-live="polite">
                  {t("teacher.search.shown").replace("{n}", students.length).replace("{total}", allStudents.length)}
                </p>
                {/* Сортировка на узком экране: заголовков таблицы там нет */}
                <div className="flex w-full flex-wrap gap-1 md:hidden" role="group" aria-label={t("teacher.search.sortBy")}>
                  {[["name", t("teacher.table.student")], ["xp", t("teacher.table.xp")], ["completed", t("teacher.table.completed")], ["lastActive", t("teacher.table.lastActive")]].map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      aria-pressed={sortKey === key}
                      onClick={() => toggleSort(key)}
                      className={`min-h-[44px] rounded-xl border px-3 text-xs font-semibold ${sortKey === key ? "border-primary bg-primary text-on-primary" : "border-border text-muted"}`}
                    >
                      {label}
                      {sortKey === key ? (direction === "asc" ? " ▲" : " ▼") : ""}
                    </button>
                  ))}
                </div>
              </div>
              {students.length === 0 ? (
                <p className="text-sm text-muted py-10 text-center">{t("teacher.search.none")}</p>
              ) : (
              <>
              {/* Заголовок таблицы — только на md+ */}
              <div className="hidden md:grid items-center grid-cols-[1.6fr_0.5fr_0.7fr_0.9fr_0.9fr_1fr_8.5rem] gap-3 px-3 pb-3 text-xs uppercase tracking-wider text-muted font-bold border-b border-border">
                <span aria-sort={ariaSort("name")}>{sortHead("name", t("teacher.table.student"))}</span>
                <span className="text-right">{t("teacher.table.level")}</span>
                <span className="text-right" aria-sort={ariaSort("xp")}>{sortHead("xp", t("teacher.table.xp"))}</span>
                <span className="text-right" aria-sort={ariaSort("completed")}>{sortHead("completed", t("teacher.table.completed"))}</span>
                <span className="text-right">{t("teacher.table.inProgress")}</span>
                <span className="text-right" aria-sort={ariaSort("lastActive")}>{sortHead("lastActive", t("teacher.table.lastActive"))}</span>
                <span className="text-right whitespace-nowrap">
                  {t("teacher.table.status")}
                </span>
              </div>

              <div className="divide-y divide-border md:divide-y-0">
                {students.map((s) => (
                  <div
                    key={s.id}
                    className="relative md:grid md:grid-cols-[1.6fr_0.5fr_0.7fr_0.9fr_0.9fr_1fr_8.5rem] md:items-center gap-3 px-1 md:px-3 py-3 md:hover:bg-panel/60 focus-within:bg-panel/60 focus-within:ring-2 focus-within:ring-primary/30 rounded-xl transition-colors"
                  >
                    {/* Имя + статус (статус виден на мобиле рядом с именем) */}
                    <div className="flex items-center justify-between gap-2 min-w-0 mb-2 md:mb-0">
                      <div className="min-w-0">
                        <Link
                          href={`/teacher/student/${s.id}`}
                          className={`${ROW_LINK} text-sm font-semibold text-text underline-offset-4 hover:text-primary hover:underline truncate block py-1.5 -my-1.5 focus:outline-none`}
                        >
                          {s.display_name || s.username}
                        </Link>
                        {s.display_name ? (
                          <p className="text-xs text-muted truncate">
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
                      <span className="font-semibold text-emerald-700 dark:text-emerald-400 tabular-nums">
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
            </>
          )}
        </div>

        <UsabilityPanel />
      </div>
    </Layout>
  );
}
