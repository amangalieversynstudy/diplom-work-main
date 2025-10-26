export default function XPBar({ current = 0, max = 100 }) {
  const pct = Math.min(100, Math.round((current / max) * 100));
  const anim = pct < 100 ? "animate-pulse" : "";
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-white/80">XP</span>
        <span className="text-sm text-white/60">
          {current} / {max}
        </span>
      </div>
      <div className="h-3 rounded-full bg-white/10 overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r from-gold to-primary transition-all ${anim}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
