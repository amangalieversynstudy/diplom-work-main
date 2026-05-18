import { useI18n } from "../lib/i18n";

export default function XPBar({ current = 0, max = 100 }) {
  const { t } = useI18n();
  const pct = Math.max(0, Math.min(100, Math.round((current / max) * 100)));
  const anim = pct > 0 && pct < 100 ? "animate-pulse" : "";

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] md:text-xs uppercase tracking-widest text-muted font-bold">
          {t("sheet.xpLabel") || "Опыт"}
        </span>
        <span className="text-sm text-text font-bold">
          {current} / {max}
        </span>
      </div>
      
      {/* Фон полоски (трек) */}
      <div className="h-3.5 md:h-4 rounded-full border overflow-hidden relative shadow-inner transition-colors duration-300"
           style={{ backgroundColor: 'var(--xpbar-track-color)', borderColor: 'var(--border)' }}>
        {/* Заполняющаяся часть */}
        <div
          className={`h-full bg-gradient-to-r from-primary to-accent transition-all duration-1000 ease-out relative ${anim}`}
          style={{ width: `${pct}%` }}
        >
          {/* Блик внутри полоски для объема */}
          <div className="absolute top-0 left-0 right-0 h-1/2 bg-white/20" />
        </div>
      </div>
    </div>
  );
}
