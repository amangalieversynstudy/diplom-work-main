import { motion } from "framer-motion";

function Node({ node, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay }}
      className="absolute"
      style={{
        left: `${node.x}%`,
        top: `${node.y}%`,
        transform: "translate(-50%, -50%)",
      }}
    >
      <div className="group">
        <div className="w-28 rounded-2xl border border-white/20 bg-black/40 backdrop-blur p-3 text-center shadow-glow">
          <div className="text-xs text-white/60 uppercase tracking-[0.3em]">{node.tier}</div>
          <div className="text-sm font-semibold">{node.name}</div>
          <div className="mt-1 h-1.5 rounded-full bg-white/10">
            <div className="h-full rounded-full bg-gradient-to-r from-white to-emerald-300" style={{ width: `${node.progress}%` }} />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function AdventureMap({ missions = [] }) {
  return (
    <div className="relative rounded-[32px] border border-white/10 bg-gradient-to-br from-[#060913] via-[#0f1628] to-[#04050a] overflow-hidden h-[420px]">
      <div className="absolute inset-0 opacity-40" aria-hidden>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(124,58,237,0.35),transparent_55%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[length:120px_120px]" />
      </div>
      <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
        <g stroke="rgba(255,255,255,0.15)" strokeWidth="2">
          {missions.map((node, index) => {
            if (index === 0) return null;
            const prev = missions[index - 1];
            return (
              <line key={`${prev.name}-${node.name}`} x1={`${prev.x}%`} y1={`${prev.y}%`} x2={`${node.x}%`} y2={`${node.y}%`} />
            );
          })}
        </g>
      </svg>
      {missions.map((node, idx) => (
        <Node key={node.id || idx} node={node} delay={idx * 0.05} />
      ))}
    </div>
  );
}
