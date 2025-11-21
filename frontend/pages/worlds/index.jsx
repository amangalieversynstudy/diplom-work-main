import Layout from "../../components/Layout";
import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Tracks } from "../../lib/api";
import Card from "../../components/Card";
import Button from "../../components/Button";
import { Compass, MapPin } from "lucide-react";
import { toast } from "sonner";
import { useDictionary } from "../../lib/i18n";

function Island({ id, name, progress, theme, difficulty, milestone, labels = { milestone: "Next milestone", progress: "Progress" } }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="relative group"
    >
      <Link href={`/worlds/${id}`} className="block h-full">
        <div
          className={`h-full rounded-3xl border border-white/10 bg-gradient-to-br ${theme} p-6 flex flex-col justify-between shadow-card hover:border-white/30 transition`}
        >
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-white/70">
              {difficulty}
            </p>
            <h3 className="text-2xl font-semibold mt-2">{name}</h3>
            <p className="text-sm text-white/70">
              {labels.milestone}: {milestone}
            </p>
          </div>
          <div>
            <div className="flex items-center justify-between text-xs text-white/60 mb-1">
              <span>{labels.progress}</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-white to-accent"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

const themes = [
  "from-indigo-900/60 via-primary/20 to-sky-500/20",
  "from-emerald-800/60 via-emerald-500/20 to-emerald-300/20",
  "from-rose-900/60 via-orange-500/20 to-amber-200/20",
  "from-slate-900/60 via-fuchsia-500/20 to-sky-300/20",
];

const defaultTiers = ["Novice Isles", "Adept Frontier", "Mythic Expanse", "Elder Rift"];

export default function WorldsPage() {
  const [tracks, setTracks] = useState([]);
  const [activeTrackId, setActiveTrackId] = useState(null);
  const [loading, setLoading] = useState(true);
  const dict = useDictionary();
  const copy = dict.worldsPage;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Tracks.list()
      .then((data) => {
        if (cancelled) return;
        const list = data || [];
        setTracks(list);
        if (list.length) {
          setActiveTrackId((prev) => prev ?? list[0].id);
        }
      })
      .catch((error) => {
        if (cancelled) return;
        console.error("Failed to fetch tracks", error);
        toast.error(`${dict.common.errorBackend}`);
        setTracks([]);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [dict.common.errorBackend]);

  const activeTrack = useMemo(
    () => tracks.find((t) => t.id === activeTrackId),
    [tracks, activeTrackId]
  );

  const tierNames = copy.tiers?.length ? copy.tiers : defaultTiers;
  const islandLabels = {
    milestone: copy.nextMilestoneLabel,
    progress: copy.progressLabel,
  };

  const worlds = useMemo(() => {
    const list = activeTrack?.worlds || [];
    return list.map((loc, i) => {
      const missions = loc.missions || [];
      const total = missions.length || 1;
      const completed = missions.filter((m) => m.user_progress?.completed).length;
      const progress = Math.round((completed / total) * 100);
      return {
        id: loc.id,
        name: loc.title,
        progress,
        theme: activeTrack?.color_theme || themes[i % themes.length],
        difficulty: tierNames[i % tierNames.length],
        milestone: missions[0]?.title || copy.defaultMilestone,
      };
    });
  }, [activeTrack, tierNames, copy.defaultMilestone]);

  return (
    <Layout>
      <section className="mb-6">
        <div className="flex flex-wrap gap-3">
          {tracks.map((track) => (
            <button
              key={track.id}
              onClick={() => setActiveTrackId(track.id)}
              className={`px-4 py-2 rounded-full border text-sm transition ${
                activeTrackId === track.id
                  ? "border-accent text-white bg-accent/20"
                  : "border-white/10 text-white/70 hover:border-white/40"
              }`}
            >
              {track.title}
              {track.is_premium && copy.premium}
            </button>
          ))}
        </div>
      </section>
      <section className="mb-8 grid gap-6 md:grid-cols-[1.1fr,0.9fr]">
        <Card
          tone="aurora"
          title={activeTrack?.title || copy.atlasTitle}
          subtitle={activeTrack?.tagline || copy.atlasSubtitle}
        >
          <p className="text-white/80 text-sm">
            {activeTrack?.description || copy.atlasFallback}
          </p>
          <div className="mt-4 flex gap-3">
            <Button onClick={() => (window.location.href = "/missions/1")}
              className="shadow-lg">
              <Compass size={18} /> {copy.autoRoute}
            </Button>
            <Button
              variant="outline"
              onClick={() => (window.location.href = "/profile")}
            >
              {copy.inspect}
            </Button>
          </div>
        </Card>
        <Card tone="night" title={copy.signalsTitle} subtitle={copy.signalsSubtitle}>
          <ul className="text-sm text-white/80 space-y-2">
            {activeTrack?.is_premium && <li>{copy.premiumSignal}</li>}
            {copy.signals.map((signal, idx) => (
              <li key={idx + signal}>{signal}</li>
            ))}
          </ul>
        </Card>
      </section>

      <section>
        <div className="flex items-center gap-3 mb-4">
          <MapPin className="text-accent" />
          <h1 className="text-2xl font-semibold">{copy.mapTitle}</h1>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {worlds.map((w) => (
            <Island key={w.id} {...w} labels={islandLabels} />
          ))}
        </div>
        {loading && (
          <p className="text-white/60 text-sm mt-4">
            {copy.loading}
          </p>
        )}
        {!loading && !worlds.length && (
          <p className="text-white/60 text-sm mt-4">
            {copy.empty}
          </p>
        )}
      </section>
    </Layout>
  );
}
