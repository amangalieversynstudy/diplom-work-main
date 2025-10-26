import Layout from "../../components/Layout";
import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Locations } from "../../lib/api";

function Island({ id, name, progress, theme }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="relative group"
    >
      <Link href={`/worlds/${id}`} className="block">
        <div
          className={`rounded-2xl p-6 h-40 flex flex-col justify-between border border-white/10 bg-gradient-to-br ${theme} shadow-lg hover:shadow-xl transition-shadow`}
        >
          <div className="text-xl font-semibold">{name}</div>
          <div>
            <div className="h-2 bg-white/20 rounded">
              <div
                className="h-full bg-white rounded"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="text-xs text-white/80 mt-1">
              Progress: {progress}%
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

const themes = [
  "from-sky-500/20 to-indigo-700/30",
  "from-emerald-500/20 to-teal-700/30",
  "from-amber-500/20 to-orange-700/30",
  "from-pink-500/20 to-rose-700/30",
];

export default function WorldsPage() {
  const [worlds, setWorlds] = useState([]);

  useEffect(() => {
    Locations.list().then((data) => {
      const ws = (data || []).map((loc, i) => {
        const missions = loc.missions || [];
        const total = missions.length || 1;
        const completed = missions.filter(
          (m) => m.user_progress?.completed
        ).length;
        const progress = Math.round((completed / total) * 100);
        return {
          id: loc.id,
          name: loc.title,
          progress,
          theme: themes[i % themes.length],
        };
      });
      setWorlds(ws);
    });
  }, []);
  return (
    <Layout>
      <h1 className="text-2xl font-semibold mb-4">World Map</h1>
      <div className="grid md:grid-cols-3 gap-6">
        {worlds.map((w) => (
          <Island key={w.id} {...w} />
        ))}
      </div>
    </Layout>
  );
}
