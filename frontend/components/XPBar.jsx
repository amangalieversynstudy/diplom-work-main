import { useI18n } from "../lib/i18n";

export default function XPBar({ current = 0, max = 100 }) {
  const { t } = useI18n();
  const pct = Math.min(100, Math.round((current / max) * 100));
  const anim = pct < 100 ? "animate-pulse" : "";
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs uppercase tracking-[0.3em] text-white/60">
          {t("sheet.xpLabel")}
        </span>
        <span className="text-sm text-white/70">
          {current} / {max}
        </span>
      </div>
      <div className="h-3 rounded-full bg-white/5 border border-white/10 overflow-hidden relative">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.08)_5%,transparent_5%)] opacity-30" />
        <div
          className={`h-full bg-gradient-to-r from-gold via-amber-300 to-accent transition-all duration-500 shadow-glow ${anim}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
