import { useCallback, useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import EmptyScroll from "../components/EmptyScroll";
import { LeaderboardAPI, Profile, Tracks } from "../lib/api";
import { getTokens } from "../lib/auth";
import { useDictionary } from "../lib/i18n";
import { Trophy, Medal, Flame, RefreshCw, User } from "lucide-react";
import { toast } from "sonner";

const GLOBAL = "global";

export default function Leaderboard() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scope, setScope] = useState(GLOBAL); // "global" или slug курса
  const [courses, setCourses] = useState([]);
  const [meId, setMeId] = useState(null);
  const latestRequest = useRef(0);
  const dict = useDictionary();
  const copy = dict.leaderboard;
  const worldsCopy = dict.worldsPage || {};
  // Класс подписан так же, как на странице выбора класса и в профиле, а не именем из базы:
  // оно одно на всех языках и не совпадало бы с тем, что ученик выбрал.
  const classNames = dict.profile?.classes || {};

  const loadData = useCallback(async (isRefresh = false) => {
    const request = ++latestRequest.current;
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      // Общий зачёт и зачёты курсов лежат в одной таблице: без выбора зачёта один человек
      // попадал бы в список по несколько раз.
      const res = await LeaderboardAPI.list(scope === GLOBAL ? { scope: GLOBAL } : { track: scope });
      if (request !== latestRequest.current) return; // пока ждали, выбрали другой зачёт
      setData(res || []);
      if (isRefresh) toast.success(copy.successRefreshed || "Обновлено");
    } catch {
      if (request !== latestRequest.current) return;
      toast.error(copy.errors?.load || "Ошибка загрузки лидерборда");
    } finally {
      if (request === latestRequest.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [copy, scope]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Список курсов для переключателя; без него остаётся общий зачёт.
  useEffect(() => {
    let cancelled = false;
    Tracks.list()
      .then((list) => {
        if (!cancelled) setCourses(list.filter((track) => track.slug));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Кто «я», чтобы найти свою строку; таблица открыта и гостям, им искать себя не нужно.
  useEffect(() => {
    if (!getTokens().access) return undefined;
    let cancelled = false;
    Profile.me()
      .then((me) => {
        if (!cancelled) setMeId(me?.id ?? me?.user?.id ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Подсветка призёров. Оттенки 700–800 в светлой теме: жёлтый и серебристый 400–500 на светлом
  // фоне давали 1,6–2,1:1.
  const getRankStyle = (index) => {
    if (index === 0) return "text-yellow-800 dark:text-yellow-400 bg-yellow-500/10 border-yellow-500/30";
    if (index === 1) return "text-slate-700 dark:text-slate-300 bg-slate-400/10 border-slate-400/30";
    if (index === 2) return "text-amber-800 dark:text-amber-500 bg-amber-600/10 border-amber-600/30";
    return "text-muted bg-panel border-border";
  };

  // с одним курсом отдельный зачёт курса совпал бы с общим, переключать нечего
  const scopes = courses.length > 1
    ? [{ id: GLOBAL, label: copy.filters.all }, ...courses.map((track) => ({ id: track.slug, label: track.title }))]
    : [];

  return (
    <Layout>
      <div className="max-w-4xl mx-auto pt-24 pb-10 px-4 transition-colors duration-300">

        {/* ── Заголовок ── */}
        <header className="mb-10 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-primary/10 border border-primary/20 text-primary mb-6 shadow-[0_0_30px_var(--primary-selection)]">
            <Trophy size={32} />
          </div>
          <p className="text-xs uppercase tracking-widest text-primary mb-3">
            {copy.eyebrow}
          </p>
          <h1 className="text-4xl md:text-5xl font-title text-text mb-4">
            {copy.title}
          </h1>
          <p className="text-muted max-w-lg mx-auto">
            {copy.subtitle}
          </p>
        </header>

        {/* ── Зачёт и обновление ── */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2 bg-panel rounded-2xl border border-border mb-8 transition-colors duration-300">
          {scopes.length > 0 ? (
            <div role="group" aria-label={copy.filters.scope} className="flex flex-wrap gap-1">
              {scopes.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={scope === item.id}
                  onClick={() => setScope(item.id)}
                  className={`min-h-[44px] px-4 rounded-xl border text-sm font-semibold transition-colors ${
                    scope === item.id
                      ? "border-primary bg-primary text-on-primary"
                      : "border-border text-muted hover:text-text hover:bg-surface/50"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : (
            <span />
          )}
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex min-h-[44px] items-center gap-2 px-4 py-2.5 text-sm font-semibold text-muted hover:text-text hover:bg-surface/50 rounded-xl transition-all w-full sm:w-auto justify-center"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} aria-hidden="true" />
            {refreshing ? copy.filters.refreshing : copy.filters.refresh}
          </button>
        </div>

        {/* ── Список лидеров ── */}
        {loading ? (
          // Скелетон на токенах темы: он должен быть светлым в светлой теме
          <div role="status" aria-busy="true" className="space-y-3">
            <span className="sr-only">{copy.loading}</span>
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4 md:p-5 rounded-2xl border border-border bg-surface animate-pulse">
                <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-border" />
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="h-4 bg-border rounded w-1/3" />
                  <div className="h-3 bg-border rounded w-1/4" />
                </div>
                <div className="flex items-center gap-6 text-right">
                  <div className="hidden sm:block space-y-2">
                    <div className="h-2 bg-border rounded w-12 ml-auto" />
                    <div className="h-4 bg-border rounded w-8 ml-auto" />
                  </div>
                  <div className="space-y-2">
                    <div className="h-2 bg-border rounded w-10 ml-auto" />
                    <div className="h-6 bg-border rounded w-14 ml-auto" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : data.length === 0 ? (
          // Пустое состояние
          <EmptyScroll icon={Trophy}>{copy.empty}</EmptyScroll>
        ) : (
          // Строки игроков
          <ol className="space-y-3">
            {data.map((entry, index) => {
              // медаль за нулевой счёт была бы насмешкой: призовые места только у тех, кто набрал XP
              const isTop3 = index < 3 && (entry.xp || 0) > 0;
              const rankStyle = getRankStyle(isTop3 ? index : 3);
              const isMe = meId != null && entry.user === meId;
              const classLabel = classNames[entry.class_role_id] || entry.class_role;

              return (
                <li
                  key={entry.id || index}
                  aria-current={isMe ? "true" : undefined}
                  className={`group flex items-center gap-4 p-4 md:p-5 rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 ${
                    isMe
                      ? "bg-surface border-primary ring-1 ring-primary/40"
                      : isTop3
                        ? "bg-surface shadow-sm border-transparent"
                        : "bg-surface border-border"
                  }`}
                >
                  {/* Плашка с местом: у призёров рядом с цифрой медаль, место не держится на одном цвете */}
                  <div className={`flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-xl border font-display font-bold transition-colors duration-300 ${
                    isTop3 ? "flex-col gap-0.5 text-sm leading-none" : "text-xl"
                  } ${rankStyle}`}>
                    {isTop3 && <Medal size={16} aria-hidden="true" />}
                    {`#${index + 1}`}
                  </div>

                  {/* Информация об игроке */}
                  <div className="flex-1 min-w-0">
                    <h3 className="flex items-center gap-2 text-lg font-bold text-text group-hover:text-primary transition-colors">
                      <span className="truncate">
                        {entry.username || entry.player || worldsCopy.heroFallback || "Неизвестный герой"}
                      </span>
                      {isMe && (
                        <span className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs font-bold text-on-primary">
                          {copy.you}
                        </span>
                      )}
                    </h3>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs md:text-sm text-muted">
                      <span className="flex items-center gap-1">
                        <User size={14} className="opacity-70" aria-hidden="true" /> {copy.columns.level} {entry.level || 1}
                      </span>
                      {/* Класс показываем, только если он выбран: выдуманное звание всем подряд вводило бы в заблуждение */}
                      {classLabel && (
                        <>
                          <span className="w-1 h-1 rounded-full bg-border" aria-hidden="true" />
                          <span className="truncate">{classLabel}</span>
                        </>
                      )}
                      {/* На узком экране колонки серии нет, а от неё зависит место при равном XP */}
                      <span className="flex items-center gap-1 text-accent sm:hidden">
                        <Flame size={14} aria-hidden="true" />
                        <span className="sr-only">{copy.columns.streak}: </span>
                        {entry.streak || 0}
                      </span>
                    </div>
                  </div>

                  {/* Статистика (Серия и Опыт) */}
                  <div className="flex items-center gap-6 text-right">
                    <div className="hidden sm:block">
                      <p className="text-xs uppercase tracking-widest text-faint mb-1">{copy.columns.streak}</p>
                      <p className="flex items-center justify-end gap-1 font-bold text-accent">
                        {entry.streak || 0} <Flame size={14} aria-hidden="true" />
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-widest text-faint mb-1">{copy.columns.xp}</p>
                      <p className="font-display text-xl font-bold text-primary">
                        {entry.xp || 0}
                      </p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </Layout>
  );
}
