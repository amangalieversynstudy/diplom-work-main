import { useI18n } from "../lib/i18n";

export default function XPBar({ current = 0, max = 100 }) {
  const { t } = useI18n();
  const pct = Math.min(100, Math.round((current / max) * 100));

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-[0.35em] text-mist/40">
          {t("sheet.xpLabel")}
        </span>
        <span className="text-xs font-mono text-primary">
          {current} / {max}
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-panel border border-primary/12 overflow-hidden relative">
        {/* tick marks */}
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "repeating-linear-gradient(90deg, rgba(46,204,138,0.4) 0px, rgba(46,204,138,0.4) 1px, transparent 1px, transparent 20px)",
          }}
        />
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #1AA870, #2ECC8A, #D4A853)",
            boxShadow: "0 0 12px rgba(46,204,138,0.5)",
          }}
        />
      </div>
    </div>
  );
}
