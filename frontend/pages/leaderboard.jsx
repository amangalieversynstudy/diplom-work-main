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
  // Подиум нужен, когда первая тройка набрала опыт: медаль за нулевой счёт была бы насмешкой.
  const hasPodium = data.length >= 3 && data.slice(0, 3).every((e) => (e.xp || 0) > 0);
  const podium = hasPodium ? data.slice(0, 3) : [];
  const rest = hasPodium ? data.slice(3) : data;
  const offset = hasPodium ? 3 : 0;
  // порядок на сцене: второе, первое, третье место; в разметке остаётся порядок по местам
  const PODIUM_VIEW = [
    { order: "order-2", plinth: "h-16" },
    { order: "order-1", plinth: "h-24" },
    { order: "order-3", plinth: "h-10" },
  ];

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
          <>
          {hasPodium && (
            <ol className="mb-6 grid grid-cols-3 items-end gap-2 sm:gap-4">
              {podium.map((entry, index) => {
                const view = PODIUM_VIEW[index];
                const isMe = meId != null && entry.user === meId;
                return (
                  <li
                    key={entry.id || index}
                    aria-current={isMe ? "true" : undefined}
                    className={`${view.order} flex min-w-0 flex-col`}
                  >
                    <div
                      className={`scroll-frame px-2 py-3 text-center sm:px-4 ${isMe ? "outline outline-2 outline-offset-2 outline-primary" : ""}`}
                    >
                      <Medal size={22} className="mx-auto text-[var(--wax)]" aria-hidden="true" />
                      <p className="mt-1 truncate font-title text-base text-text sm:text-lg">
                        {entry.username || entry.player || worldsCopy.heroFallback || "Неизвестный герой"}
                      </p>
                      {isMe && (
                        <span className="mt-1 inline-block rounded-full bg-primary px-2 py-0.5 text-xs font-bold text-on-primary">
                          {copy.you}
                        </span>
                      )}
                      <p className="mt-1 text-xs text-muted">
                        {copy.columns.level} {entry.level || 1}
                      </p>
                      <p className="font-title text-xl text-primary">{entry.xp || 0} {copy.columns.xp}</p>
                    </div>
                    <div
                      className={`${view.plinth} flex items-start justify-center rounded-b-md border-x-2 border-b-2 border-[var(--ink)] bg-[var(--gold-frame)] pt-2 font-title text-2xl text-[var(--ink-deep)]`}
                    >
                      {`#${index + 1}`}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
          {/* Строки игроков */}
          <ol className="space-y-3" start={offset + 1}>
            {rest.map((entry, restIndex) => {
              const index = restIndex + offset;
              // медаль за нулевой счёт была бы насмешкой: призовые места только у тех, кто набрал XP
              const isTop3 = index < 3 && (entry.xp || 0) > 0;
              const isMe = meId != null && entry.user === meId;
              const classLabel = classNames[entry.class_role_id] || entry.class_role;

              return (
                <li
                  key={entry.id || index}
                  aria-current={isMe ? "true" : undefined}
                  className={`scroll-frame group flex items-center gap-4 p-4 md:p-5 ${
                    isMe ? "outline outline-2 outline-offset-2 outline-primary" : ""
                  }`}
                >
                  {/* Плашка с местом: у призёров рядом с цифрой медаль, место не держится на одном цвете */}
                  <div className={`flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-xl border font-title text-text bg-panel border-border ${
                    isTop3 ? "flex-col gap-0.5 text-sm leading-none" : "text-xl"
                  }`}>
                    {isTop3 && <Medal size={16} className="text-[var(--wax)]" aria-hidden="true" />}
                    {`#${index + 1}`}
                  </div>

                  {/* Информация об игроке */}
                  <div className="flex-1 min-w-0">
                    <h3 className="flex items-center gap-2 font-title text-xl text-text">
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
                      <span className="flex items-center gap-1 text-[var(--wax)] sm:hidden">
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
                      <p className="flex items-center justify-end gap-1 font-bold text-[var(--wax)]">
                        {entry.streak || 0} <Flame size={14} aria-hidden="true" />
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-widest text-faint mb-1">{copy.columns.xp}</p>
                      <p className="font-title text-xl text-primary">
                        {entry.xp || 0}
                      </p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          </>
        )}
      </div>
    </Layout>
  );
}
