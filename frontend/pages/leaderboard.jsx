import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { LeaderboardAPI } from "../lib/api";
import { useDictionary } from "../lib/i18n";
import { Trophy, Medal, Flame, RefreshCw, User } from "lucide-react";
import { toast } from "sonner";

export default function Leaderboard() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [period, setPeriod] = useState("all_time");
  const dict = useDictionary();
  const copy = dict.leaderboard;

  const loadData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const res = await LeaderboardAPI.list({ period });
      setData(res || []);
      if (isRefresh) toast.success(copy.successRefreshed || "Обновлено");
    } catch (err) {
      toast.error(copy.errors?.load || "Ошибка загрузки лидерборда");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [period]);

  // Функция для красивой подсветки Топ-3 игроков
  const getRankStyle = (index) => {
    if (index === 0) return "text-yellow-500 bg-yellow-500/10 border-yellow-500/20";
    if (index === 1) return "text-slate-400 bg-slate-400/10 border-slate-400/20";
    if (index === 2) return "text-amber-600 bg-amber-600/10 border-amber-600/20";
    return "text-muted bg-panel border-border";
  };

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
          <h1 className="text-4xl md:text-5xl font-display font-bold text-text mb-4">
            {copy.title}
          </h1>
          <p className="text-muted max-w-lg mx-auto">
            {copy.subtitle}
          </p>
        </header>

        {/* ── Фильтры ── */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-2 bg-panel rounded-2xl border border-border mb-8 transition-colors duration-300">
          <div className="flex gap-2 w-full sm:w-auto overflow-x-auto hide-scrollbar">
            {Object.entries(copy.filters.periodOptions).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setPeriod(key)}
                className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all whitespace-nowrap ${
                  period === key
                    ? "bg-surface text-text shadow-sm border border-border"
                    : "text-muted hover:text-text hover:bg-surface/50 border border-transparent"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-muted hover:text-text hover:bg-surface/50 rounded-xl transition-all w-full sm:w-auto justify-center"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? copy.filters.refreshing : copy.filters.refresh}
          </button>
        </div>

        {/* ── Список лидеров ── */}
        <div className="space-y-3">
          {loading ? (
            // Скелетон-загрузчик
            [...Array(5)].map((_, i) => (
              <div key={i} className="h-20 bg-panel animate-pulse rounded-2xl border border-border" />
            ))
          ) : data.length === 0 ? (
            // Пустое состояние
            <div className="text-center py-20 bg-panel rounded-3xl border border-border transition-colors duration-300">
              <Trophy size={48} className="mx-auto text-faint mb-4 opacity-50" />
              <p className="text-muted">{copy.empty}</p>
            </div>
          ) : (
            // Строки игроков
            data.map((user, index) => {
              const rankStyle = getRankStyle(index);
              const isTop3 = index < 3;

              return (
                <div
                  key={user.id || index}
                  className={`group flex items-center gap-4 p-4 md:p-5 rounded-2xl border bg-surface transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/30 ${
                    isTop3 ? "shadow-sm border-transparent" : "border-border"
                  }`}
                >
                  {/* Плашка с местом */}
                  <div className={`flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-xl border font-display text-xl font-bold transition-colors duration-300 ${rankStyle}`}>
                    {isTop3 ? <Medal size={24} /> : `#${index + 1}`}
                  </div>

                  {/* Информация об игроке */}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-text truncate group-hover:text-primary transition-colors">
                      {user.username || user.player || "Неизвестный герой"}
                    </h3>
                    <div className="flex items-center gap-3 text-xs md:text-sm text-muted mt-1">
                      <span className="flex items-center gap-1">
                        <User size={14} className="opacity-70" /> {copy.columns.level} {user.level || 1}
                      </span>
                      <span className="w-1 h-1 rounded-full bg-border" />
                      <span className="truncate">{user.class_role || "Академик"}</span>
                    </div>
                  </div>

                  {/* Статистика (Серия и Опыт) */}
                  <div className="flex items-center gap-6 text-right">
                    <div className="hidden sm:block">
                      <p className="text-[10px] uppercase tracking-widest text-faint mb-1">{copy.columns.streak}</p>
                      <p className="flex items-center justify-end gap-1 font-bold text-accent">
                        {user.streak || 0} <Flame size={14} />
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-faint mb-1">{copy.columns.xp}</p>
                      <p className="font-display text-xl font-bold text-primary">
                        {user.xp || 0}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </Layout>
  );
}