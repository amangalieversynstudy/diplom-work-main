import Layout from "../../components/Layout";
import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Locations } from "../../lib/api";
import Card from "../../components/Card";
import Button from "../../components/Button";
import { Compass, MapPin } from "lucide-react";

function Island({ id, name, progress, theme, difficulty, milestone }) {
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
            <p className="text-sm text-white/70">Next milestone: {milestone}</p>
          </div>
          <div>
            <div className="flex items-center justify-between text-xs text-white/60 mb-1">
              <span>Progress</span>
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

const tiers = ["Novice Isles", "Adept Frontier", "Mythic Expanse", "Elder Rift"];

export default function WorldsPage() {
  const [worlds, setWorlds] = useState([]);

  useEffect(() => {
    Locations.list().then((data) => {
      const ws = (data || []).map((loc, i) => {
        const missions = loc.missions || [];
        const total = missions.length || 1;
        const completed = missions.filter((m) => m.user_progress?.completed)
          .length;
        const progress = Math.round((completed / total) * 100);
        return {
          id: loc.id,
          name: loc.title,
          progress,
          theme: themes[i % themes.length],
          difficulty: tiers[i % tiers.length],
          milestone: missions[0]?.title || "Intro quest",
        };
      });
      setWorlds(ws);
    });
  }, []);

  return (
    <Layout>
      <section className="mb-8 grid gap-6 md:grid-cols-[1.1fr,0.9fr]">
        <Card tone="aurora" title="Atlas" subtitle="Chart the archipelago of knowledge">
          <p className="text-white/80 text-sm">
            Each world focuses on a different progression arc: fundamentals, backend mastery,
            DevOps rituals, and boss fights that mimic real interview scenarios.
          </p>
          <div className="mt-4 flex gap-3">
            <Button onClick={() => (window.location.href = "/missions/1")}
              className="shadow-lg">
              <Compass size={18} /> Auto-route to first mission
            </Button>
            <Button
              variant="outline"
              onClick={() => (window.location.href = "/profile")}
            >
              Inspect Character
            </Button>
          </div>
        </Card>
        <Card tone="night" title="World Signals" subtitle="Live scouting data">
          <ul className="text-sm text-white/80 space-y-2">
            <li>⚔️ Intro Gate requires Class alignment</li>
            <li>🌊 Celery Reef stable – jobs succeed 99%</li>
            <li>🌋 Boss world unlocking at 75% completion</li>
          </ul>
        </Card>
      </section>

      <section>
        <div className="flex items-center gap-3 mb-4">
          <MapPin className="text-accent" />
          <h1 className="text-2xl font-semibold">World Map</h1>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {worlds.map((w) => (
            <Island key={w.id} {...w} />
          ))}
        </div>
        {!worlds.length && (
          <p className="text-white/60 text-sm mt-4">
            Loading scouting intel…
          </p>
        )}
      </section>
    </Layout>
  );
}
