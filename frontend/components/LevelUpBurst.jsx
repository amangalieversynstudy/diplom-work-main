import { useEffect } from "react";
import { useI18n } from "../lib/i18n";

/**
 * LevelUpBurst — праздничный оверлей при повышении уровня.
 *
 * Показывается поверх страницы миссии, когда бэкенд вернул leveled_up.
 * Самодостаточный (CSS-анимации, без библиотек), не перехватывает клики
 * (pointer-events-none) и сам гаснет через `duration` мс, дёргая onDone.
 */
export default function LevelUpBurst({ level, onDone, duration = 2600 }) {
  const { t } = useI18n();

  useEffect(() => {
    const id = setTimeout(() => onDone?.(), duration);
    return () => clearTimeout(id);
  }, [duration, onDone]);

  return (
    <div
      className="lvlup-overlay fixed inset-0 z-[60] flex items-center justify-center pointer-events-none"
      role="status"
      aria-live="polite"
    >
      <div className="lvlup-rays absolute" aria-hidden="true" />
      <div className="lvlup-card relative flex flex-col items-center gap-1.5 px-10 py-7 rounded-3xl border border-amber-300/40 bg-[#0c1224]/85 backdrop-blur-xl shadow-[0_0_60px_rgba(255,200,90,0.45)]">
        <span className="lvlup-spark text-2xl" aria-hidden="true">
          ✦
        </span>
        <p className="text-amber-300 text-xs font-bold tracking-[0.35em] uppercase">
          {t("missionPage.levelUpTitle")}
        </p>
        <p className="text-white font-display text-4xl sm:text-5xl font-extrabold drop-shadow">
          {t("missionPage.levelLabel")} {level}
        </p>
      </div>

      <style jsx>{`
        .lvlup-overlay {
          animation: lvlup-fade 2.6s ease forwards;
        }
        @keyframes lvlup-fade {
          0% { opacity: 0; }
          8% { opacity: 1; }
          85% { opacity: 1; }
          100% { opacity: 0; }
        }
        .lvlup-card {
          animation: lvlup-pop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both;
        }
        @keyframes lvlup-pop {
          0% { transform: scale(0.6); opacity: 0; }
          60% { transform: scale(1.08); }
          100% { transform: scale(1); opacity: 1; }
        }
        .lvlup-rays {
          width: 140vmax;
          height: 140vmax;
          background: conic-gradient(
            from 0deg,
            rgba(255, 210, 120, 0) 0 8deg,
            rgba(255, 210, 120, 0.16) 8deg 16deg
          );
          border-radius: 50%;
          animation: lvlup-spin 6s linear infinite;
          -webkit-mask: radial-gradient(circle, transparent 16%, #000 22%);
          mask: radial-gradient(circle, transparent 16%, #000 22%);
        }
        @keyframes lvlup-spin {
          to { transform: rotate(360deg); }
        }
        .lvlup-spark {
          color: #ffe9a8;
          animation: lvlup-spark 1.2s ease-in-out infinite;
        }
        @keyframes lvlup-spark {
          0%, 100% { transform: scale(1); opacity: 0.8; }
          50% { transform: scale(1.3); opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .lvlup-overlay { animation: none; opacity: 1; }
          .lvlup-card,
          .lvlup-rays,
          .lvlup-spark { animation: none; }
        }
      `}</style>
    </div>
  );
}
