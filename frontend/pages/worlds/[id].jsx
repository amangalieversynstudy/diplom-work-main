import Layout from "../../components/Layout";
import Button from "../../components/Button";
import Link from "next/link";
import { useRouter } from "next/router";
import Badge from "../../components/Badge";
import Card from "../../components/Card";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Locations, missionStatus } from "../../lib/api";
import { Compass } from "lucide-react";

const statusColor = {
  completed: "from-emerald-400 to-emerald-600",
  available: "from-primary to-accent",
  locked: "from-white/40 to-white/10",
};

const statusLabel = {
  completed: "Completed",
  available: "Available",
  locked: "Locked",
};

export default function WorldMapPage() {
  const router = useRouter();
  const { id } = router.query;
  const [loc, setLoc] = useState(null);
  const [missions, setMissions] = useState([]);

  useEffect(() => {
    if (!id) return;
    Locations.get(id).then((d) => {
      setLoc(d);
      const ms = (d.missions || []).map((m, i) => ({
        id: m.id,
        name: m.title,
        status: missionStatus(m),
        x: typeof m.pos_x === "number" ? m.pos_x : 10 + i * 20,
        y: typeof m.pos_y === "number" ? m.pos_y : 70 - i * 15,
      }));
      setMissions(ms);
    });
  }, [id]);

  return (
    <Layout>
      <section className="mb-6 grid gap-4 md:grid-cols-[2fr,1fr]">
        <Card
          tone="aurora"
          title={loc?.title || `World ${id}`}
          subtitle="Mission topology"
        >
          <p className="text-sm text-white/80">
            Nodes align with backend missions pulled from the live API. Complete them in order to
            unlock the Gate and reveal capstone boss fights.
          </p>
          <div className="flex gap-3 mt-4 text-xs">
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/15">
              <span className="w-3 h-3 rounded-full bg-success" /> Completed
            </span>
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/15">
              <span className="w-3 h-3 rounded-full bg-primary" /> Available
            </span>
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/15">
              <span className="w-3 h-3 rounded-full bg-white/20" /> Locked
            </span>
          </div>
        </Card>
        <Card tone="night" title="Scout Log" subtitle="Live intel">
          <ul className="text-sm text-white/80 space-y-2">
            <li>⚙️ Missions synced: {missions.length}</li>
            <li>🧭 Recommended level: {loc?.recommended_level || "1-5"}</li>
            <li>📡 Environment: {loc?.environment || "Stable"}</li>
          </ul>
        </Card>
      </section>

      <div className="relative rounded-3xl border border-white/15 bg-[#050814]/70 h-[460px] overflow-hidden">
        <div className="absolute inset-0 opacity-40" aria-hidden>
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.2),transparent_55%)]" />
          <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.06)_1px,transparent_1px)] bg-[length:140px_140px]" />
        </div>
        <div className="absolute top-4 left-4 text-xs uppercase tracking-[0.35em] text-white/60 inline-flex items-center gap-2">
          <Compass size={16} className="text-accent" /> Holo Map
        </div>
        <svg
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="none"
        >
          <g stroke="rgba(255,255,255,0.25)" strokeWidth="2">
            {missions.map((m, i) => {
              if (i === 0) return null;
              const p = missions[i - 1];
              return (
                <line
                  key={`ln-${p.id}-${m.id}`}
                  x1={`${p.x}%`}
                  y1={`${p.y}%`}
                  x2={`${m.x}%`}
                  y2={`${m.y}%`}
                />
              );
            })}
          </g>
        </svg>
        {missions.map((m, i) => (
          <motion.div
            key={m.id}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            className="absolute"
            style={{
              left: `${m.x}%`,
              top: `${m.y}%`,
              transform: "translate(-50%, -50%)",
            }}
          >
            <Link href={`/missions/${m.id}`} className="group">
              <div className="w-32 rounded-2xl border border-white/15 bg-black/50 backdrop-blur-lg p-3 text-center shadow-glow">
                <div
                  className={`mx-auto w-10 h-10 rounded-full mb-2 bg-gradient-to-br ${statusColor[m.status]} flex items-center justify-center text-xs font-bold`}
                >
                  {i + 1}
                </div>
                <div className="text-sm font-semibold leading-tight">{m.name}</div>
                <div className="text-xs text-white/70 mt-1">
                  <Badge status={m.status}>{statusLabel[m.status]}</Badge>
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => router.back()}>
          Back
        </Button>
        <Button onClick={() => router.push("/worlds")}>World List</Button>
      </div>
    </Layout>
  );
}
