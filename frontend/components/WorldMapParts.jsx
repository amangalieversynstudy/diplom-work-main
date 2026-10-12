import { forwardRef } from "react";

/**
 * Общие части пергаментной карты (экран /worlds и лендинг): бумажная текстура,
 * штурманская сетка и тень по краям. Кладутся внутрь relative-холста.
 */
export function MapBackdrop() {
  return (
    <>
      {/* Бумажная текстура */}
      <div className="absolute inset-0 pointer-events-none opacity-30 mix-blend-multiply rounded-[inherit]">
        <svg className="w-full h-full" aria-hidden="true">
          <filter id="paper-noise">
            <feTurbulence type="fractalNoise" baseFrequency="0.6" numOctaves="4" stitchTiles="stitch" />
          </filter>
          <rect width="100%" height="100%" filter="url(#paper-noise)" />
        </svg>
      </div>

      {/* Штурманская сетка */}
      <div
        className="absolute inset-0 opacity-15 pointer-events-none rounded-[inherit]"
        style={{
          backgroundImage:
            "linear-gradient(var(--ink) 1.5px, transparent 1.5px), linear-gradient(90deg, var(--ink) 1.5px, transparent 1.5px)",
          backgroundSize: "80px 80px",
        }}
      />

      <div className="absolute inset-0 shadow-[inset_0_0_150px_rgba(62,39,35,0.6)] pointer-events-none rounded-[inherit]" />
    </>
  );
}

/**
 * Тропа между узлами: пунктир чернилами и красная «пройденная» часть под маской.
 * На /worlds красную часть рисует GSAP (класс map-path, stroke-dashoffset 100 -> 0),
 * на лендинге тропа показана целиком (revealed). ref указывает на коричневый путь:
 * по нему герой идёт между узлами.
 */
export const MapTrail = forwardRef(function MapTrail({ d, revealed = false }, trailRef) {
  return (
    <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <mask id="path-mask">
          <path
            className="map-path"
            d={d}
            fill="none"
            stroke="white"
            strokeWidth="16"
            vectorEffect="non-scaling-stroke"
            pathLength="100"
            style={{ strokeDasharray: "100", strokeDashoffset: revealed ? "0" : "100" }}
          />
        </mask>
      </defs>

      <path
        ref={trailRef}
        d={d}
        fill="none"
        stroke="#8b5a2b"
        strokeWidth="3.5"
        strokeDasharray="6,6"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={d}
        fill="none"
        stroke="var(--wax)"
        strokeWidth="4.5"
        strokeDasharray="6,6"
        vectorEffect="non-scaling-stroke"
        mask="url(#path-mask)"
      />
    </svg>
  );
});
