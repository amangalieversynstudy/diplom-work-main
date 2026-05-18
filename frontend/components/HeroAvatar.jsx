import { memo, useMemo } from "react";
import { getAvatarConfig } from "../lib/avatar";

const gradients = {
  mage: ["#7c3aed", "#22d3ee"],
  rogue: ["#0f172a", "#22c55e"],
  knight: ["#1d4ed8", "#facc15"],
};

function HeroAvatarBase({ config, size = 240 }) {
  const merged = useMemo(() => ({ ...getAvatarConfig(), ...(config || {}) }), [config]);
  const palette = gradients[merged.archetype] || gradients.mage;
  const scale = size / 240;

  return (
    <div
      className="relative mx-auto"
      style={{ width: size, height: size * 1.15, transform: `scale(${scale})` }}
    >
      <div className="absolute inset-0 blur-3xl opacity-30" style={{ background: `radial-gradient(circle, ${merged.accent}, transparent 65%)` }} />
      <div className="relative w-[240px] h-[270px] mx-auto">
        <div
          className="absolute left-1/2 -translate-x-1/2 rounded-full"
          style={{ width: 220, height: 220, background: `radial-gradient(circle at 20% 20%, ${palette[0]}, ${palette[1]})`, opacity: 0.35 }}
        />
        <div className="absolute left-1/2 top-6 -translate-x-1/2 w-32 h-32 rounded-full" style={{ backgroundColor: merged.hair }} />
        <div className="absolute left-1/2 top-20 -translate-x-1/2 w-36 h-44 rounded-[40px] border border-white/20" style={{ background: `linear-gradient(135deg, ${merged.armor}, rgba(255,255,255,0.15))` }} />
        <div className="absolute left-1/2 top-24 -translate-x-1/2 w-10 h-10 rounded-full bg-white/80" />
        <div className="absolute left-1/2 top-[170px] -translate-x-1/2 w-40 h-4 rounded-full" style={{ background: merged.accent }} />
        <div className="absolute left-[60px] top-10 w-3 h-56 bg-gradient-to-b from-white/80 to-transparent rounded-full" />
        <div className="absolute right-[60px] top-10 w-3 h-56 bg-gradient-to-b from-white/80 to-transparent rounded-full" />
        <div
          className="absolute left-6 top-28 w-4 h-40 rounded-full"
          style={{ background: merged.weapon }}
        />
        <div className="absolute left-3 top-28 w-10 h-10 rounded-full bg-white/40" />
        <div className="absolute right-10 top-48 w-6 h-24 rounded-full bg-white/40" />
      </div>
    </div>
  );
}

const HeroAvatar = memo(HeroAvatarBase);

export default HeroAvatar;
