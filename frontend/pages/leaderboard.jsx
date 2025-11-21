import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Badge from "../components/Badge";
import Button from "../components/Button";
import { useDictionary } from "../lib/i18n";
import { LeaderboardAPI, Tracks } from "../lib/api";

export default function Leaderboard() {
  const dict = useDictionary();
  const copy = dict.leaderboard;
  const common = dict.common;
  const [rows, setRows] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [filters, setFilters] = useState({ scope: "global", period: "all_time", track: "" });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    Tracks.list()
      .then((data) => setTracks(data || []))
      .catch(() => setTracks([]));
  }, []);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    LeaderboardAPI.list({
      scope: filters.scope,
      period: filters.period,
      track: filters.scope === "track" ? filters.track || undefined : undefined,
    })
      .then((data) => {
        if (isMounted) setRows(data || []);
      })
      .catch(() => toast.error(copy.errors.load))
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [filters, copy.errors.load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await LeaderboardAPI.list({
        scope: filters.scope,
        period: filters.period,
        track: filters.scope === "track" ? filters.track || undefined : undefined,
      });
      setRows(data || []);
      toast.success(copy.successRefreshed);
    } catch (e) {
      toast.error(copy.errors.load);
    } finally {
      setRefreshing(false);
    }
  };

  const trackOptions = useMemo(
    () => [
      { value: "", label: copy.filters.trackAny },
      ...tracks.map((track) => ({ value: track.slug, label: track.title })),
    ],
    [tracks, copy.filters.trackAny]
  );

  return (
    <Layout>
      <section className="mb-6">
        <p className="text-xs uppercase tracking-[0.35em] text-white/60">
          {copy.eyebrow}
        </p>
        <h1 className="text-3xl font-display">{copy.title}</h1>
        <p className="text-sm text-white/70">{copy.subtitle}</p>
      </section>

      <Card tone="default" title={copy.filters.title} subtitle={copy.filters.subtitle}>
        <div className="grid gap-3 md:grid-cols-4">
          <label className="flex flex-col text-xs uppercase tracking-[0.3em] text-white/60">
            {copy.filters.scope}
            <select
              className="mt-1 rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-white"
              value={filters.scope}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  scope: e.target.value,
                }))
              }
            >
              <option value="global">{copy.filters.scopeOptions.global}</option>
              <option value="track">{copy.filters.scopeOptions.track}</option>
            </select>
          </label>
          <label className="flex flex-col text-xs uppercase tracking-[0.3em] text-white/60">
            {copy.filters.period}
            <select
              className="mt-1 rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-white"
              value={filters.period}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  period: e.target.value,
                }))
              }
            >
              <option value="all_time">{copy.filters.periodOptions.all_time}</option>
              <option value="weekly">{copy.filters.periodOptions.weekly}</option>
              <option value="monthly">{copy.filters.periodOptions.monthly}</option>
            </select>
          </label>
          <label className="flex flex-col text-xs uppercase tracking-[0.3em] text-white/60">
            {copy.filters.track}
            <select
              className="mt-1 rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-white"
              value={filters.track}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  track: e.target.value,
                }))
              }
              disabled={filters.scope !== "track"}
            >
              {trackOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end">
            <Button onClick={handleRefresh} disabled={refreshing} className="w-full">
              {refreshing ? copy.filters.refreshing : copy.filters.refresh}
            </Button>
          </div>
        </div>
      </Card>

      <Card tone="night" className="mt-6">
        {loading ? (
          <p className="text-sm text-white/60">{copy.loading}</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-white/60">{copy.empty}</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-white/70 text-xs uppercase tracking-[0.3em]">
              <tr>
                <th className="text-left py-3">{copy.columns.rank}</th>
                <th className="text-left">{copy.columns.player}</th>
                <th className="text-left">{copy.columns.level}</th>
                <th className="text-left">{copy.columns.xp}</th>
                <th className="text-left">{copy.columns.streak}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const level = row.user_display?.level ?? common.none;
                const xp = row.xp_total ?? row.user_display?.xp ?? 0;
                const streakValue = row.streak ?? Math.max(1, Math.round(xp / 150));
                return (
                  <tr key={row.id || `${row.user_display?.username || "user"}-${index}`} className="border-t border-white/10">
                    <td className="py-3 text-white/60">#{row.position || index + 1}</td>
                    <td className="py-3 font-semibold">
                      {row.user_display?.display_name || row.user_display?.username || "unknown"}
                    </td>
                    <td>{level}</td>
                    <td>{xp}</td>
                    <td>
                      <Badge status={streakValue > 2 ? "available" : "locked"}>{streakValue}d</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </Layout>
  );
}
