import Layout from "../../components/Layout";
import Button from "../../components/Button";
import Link from "next/link";
import { useRouter } from "next/router";
import Badge from "../../components/Badge";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Locations, missionStatus } from "../../lib/api";

const statusColor = {
  completed: "bg-success",
  available: "bg-primary",
  locked: "bg-white/30",
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
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-sm text-white/60">World</div>
          <h1 className="text-2xl font-semibold">
            {loc?.title || `World ${id}`} — Map
          </h1>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="inline-flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-success inline-block" />
            Completed
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-primary inline-block" />
            Available
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-white/20 inline-block" />
            Locked
          </span>
        </div>
      </div>

      <div className="relative rounded-2xl border border-white/10 bg-gradient-to-b from-slate-800/40 to-slate-900/60 h-[420px] overflow-hidden">
        {/* линии между нодами */}
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
        {/* ноды */}
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
              <div
                className={`w-28 rounded-xl p-3 text-center border border-white/10 bg-slate-900/60 backdrop-blur hover:bg-slate-900/80 transition shadow-lg`}
              >
                <div
                  className={`mx-auto w-3 h-3 rounded-full ${
                    statusColor[m.status]
                  } mb-2`}
                />
                <div className="text-sm font-semibold">{m.name}</div>
                <div className="text-xs text-white/70">
                  <Badge status={m.status}>{statusLabel[m.status]}</Badge>
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>

      <div className="mt-6">
        <Button variant="outline" onClick={() => router.back()}>
          Back
        </Button>
      </div>
    </Layout>
  );
}
