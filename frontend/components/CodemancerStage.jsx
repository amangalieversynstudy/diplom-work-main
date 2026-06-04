import { Heart, Droplet } from "lucide-react";

/**
 * CodemancerStage — пиксель-арт игровая сцена в стиле мокапа codemancer.html.
 *
 * Самодостаточный «экран» (тёмный ночной vibe в любой теме сайта), который
 * вставляется полосой на страницу квеста. Сцена — чистый SVG (без растровых
 * ассетов, переживёт любую сборку). HUD (портрет + HP/MP) и Level-пилюля —
 * оверлеи поверх сцены, управляются пропсами.
 *
 * Props:
 *   level   — число уровня игрока (из профиля)
 *   hpPct   — заполнение полоски HP, 0..100 (пока флейвор)
 *   mpPct   — заполнение полоски MP/маны, 0..100 (завязано на ai_summons)
 *   heroName — имя героя (для aria/подписи), по умолчанию "Alaric"
 */
export default function CodemancerStage({
  level = 1,
  hpPct = 100,
  mpPct = 100,
  heroName = "Alaric",
  phase = "idle", // idle | casting | victory | defeat — реакция на запуск кода
  tick = 0, // меняется на каждое событие, перезапускает one-shot анимации
}) {
  const clamp = (n) => Math.max(0, Math.min(100, Number(n) || 0));
  const hp = clamp(hpPct);
  const mp = clamp(mpPct);

  return (
    <div
      className="codemancer-stage relative w-full shrink-0 h-44 sm:h-52 md:h-60 xl:h-64 overflow-hidden border-b border-border bg-[#0a1322] select-none"
      role="img"
      aria-label={`${heroName}, level ${level}`}
    >
      {/* ── Пиксель-арт сцена (SVG) ─────────────────────────────── */}
      <svg
        viewBox="0 0 1408 470"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-0 w-full h-full"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="cm-sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#1a3050" />
            <stop offset=".6" stopColor="#0f1c34" />
            <stop offset="1" stopColor="#0a1322" />
          </linearGradient>
          <radialGradient id="cm-moonGlow" cx=".5" cy=".5" r=".5">
            <stop offset="0" stopColor="#fff7d6" stopOpacity=".55" />
            <stop offset="1" stopColor="#fff7d6" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="cm-mountains" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#3a4e72" />
            <stop offset="1" stopColor="#1a2640" />
          </linearGradient>
          <linearGradient id="cm-castle" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#6a7390" />
            <stop offset="1" stopColor="#2c324a" />
          </linearGradient>
          <linearGradient id="cm-ground" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#3d4a3a" />
            <stop offset="1" stopColor="#1a2418" />
          </linearGradient>
          <linearGradient id="cm-leaf" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#3e6a32" />
            <stop offset="1" stopColor="#1b3a18" />
          </linearGradient>
          <radialGradient id="cm-golemGlow" cx=".5" cy=".5" r=".5">
            <stop offset="0" stopColor="#ffd778" stopOpacity=".7" />
            <stop offset="1" stopColor="#ffd778" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* sky */}
        <rect width="1408" height="470" fill="url(#cm-sky)" />

        {/* stars */}
        <g fill="#cfd6f0" className="cm-stars">
          <circle cx="120" cy="60" r="1.2" />
          <circle cx="260" cy="40" r="1" />
          <circle cx="450" cy="80" r="1.4" />
          <circle cx="900" cy="50" r="1" />
          <circle cx="1080" cy="90" r="1.2" />
          <circle cx="1280" cy="60" r="1" />
          <circle cx="1340" cy="120" r="1.3" />
          <circle cx="780" cy="110" r="1" />
        </g>

        {/* moon */}
        <g transform="translate(700 90)">
          <circle r="60" fill="url(#cm-moonGlow)" />
          <path d="M -14 -22 a 22 22 0 1 0 0 44 a 17 17 0 1 1 0 -44 z" fill="#f7efcc" />
        </g>

        {/* distant mountains */}
        <path
          d="M 0 240 L 120 180 L 220 220 L 340 150 L 480 220 L 560 180 L 700 240 L 820 200 L 980 240 L 1100 180 L 1240 230 L 1408 200 L 1408 320 L 0 320 Z"
          fill="url(#cm-mountains)"
          opacity=".75"
        />

        {/* castle */}
        <g transform="translate(900 110)" fill="url(#cm-castle)" stroke="#1a2034" strokeWidth="1.2">
          <rect x="0" y="60" width="220" height="120" />
          <rect x="-20" y="80" width="40" height="100" />
          <rect x="220" y="80" width="40" height="100" />
          <polygon points="-25,80 -10,40 5,80" />
          <polygon points="215,80 230,40 245,80" />
          <polygon points="0,60 30,20 60,60" />
          <polygon points="160,60 190,20 220,60" />
          <polygon points="80,50 110,0 140,50" />
          <rect x="100" y="100" width="20" height="40" fill="#1a1f30" />
          <rect x="35" y="100" width="14" height="20" fill="#ffd86a" opacity=".7" />
          <rect x="175" y="100" width="14" height="20" fill="#ffd86a" opacity=".7" />
          <rect x="100" y="130" width="14" height="20" fill="#ffd86a" opacity=".7" />
        </g>

        {/* trees left */}
        <g transform="translate(40 60)">
          <rect x="58" y="220" width="22" height="120" fill="#2a1a0e" />
          <ellipse cx="70" cy="180" rx="120" ry="80" fill="url(#cm-leaf)" />
          <ellipse cx="40" cy="140" rx="80" ry="55" fill="#2e5224" />
          <ellipse cx="110" cy="150" rx="80" ry="55" fill="#264a1e" />
        </g>
        <g transform="translate(220 80)">
          <rect x="40" y="200" width="16" height="100" fill="#241510" />
          <ellipse cx="48" cy="170" rx="80" ry="55" fill="#2c5424" />
        </g>

        {/* trees right */}
        <g transform="translate(1180 70)">
          <rect x="60" y="220" width="22" height="120" fill="#2a1a0e" />
          <ellipse cx="70" cy="180" rx="130" ry="85" fill="url(#cm-leaf)" />
          <ellipse cx="120" cy="140" rx="80" ry="55" fill="#2e5224" />
          <ellipse cx="30" cy="150" rx="80" ry="55" fill="#264a1e" />
        </g>

        {/* ruins / arches */}
        <g fill="#5a6478" opacity=".9">
          <rect x="380" y="240" width="20" height="80" />
          <rect x="450" y="240" width="20" height="80" />
          <rect x="372" y="232" width="106" height="14" />
          <rect x="580" y="250" width="18" height="70" />
          <rect x="640" y="250" width="18" height="70" />
          <rect x="574" y="244" width="90" height="12" />
        </g>

        {/* foreground platform (left) */}
        <g>
          <path
            d="M 0 380 L 0 470 L 600 470 L 600 360 Q 540 370 500 360 Q 440 348 380 360 Q 300 374 240 360 Q 160 348 100 360 Q 50 368 0 360 Z"
            fill="url(#cm-ground)"
          />
          <path
            d="M 0 360 Q 60 348 100 354 Q 170 364 240 354 Q 310 344 380 354 Q 440 360 500 354 Q 560 348 600 358 L 600 366 Q 540 358 480 364 Q 410 372 340 364 Q 270 358 200 366 Q 130 374 60 366 L 0 370 Z"
            fill="#5a8a3a"
            opacity=".75"
          />
          <ellipse cx="120" cy="400" rx="40" ry="14" fill="#1f2a1e" />
          <ellipse cx="320" cy="410" rx="50" ry="14" fill="#1f2a1e" />
        </g>

        {/* spikes pit */}
        <g transform="translate(620 320)">
          <g fill="#cfd4dc" stroke="#7a8090" strokeWidth="1">
            <polygon points="0,80 14,20 28,80" />
            <polygon points="26,80 40,12 54,80" />
            <polygon points="52,80 66,18 80,80" />
            <polygon points="78,80 92,8 106,80" />
            <polygon points="104,80 118,16 132,80" />
            <polygon points="130,80 144,10 158,80" />
            <polygon points="156,80 170,18 184,80" />
          </g>
        </g>

        {/* foreground platform (right) */}
        <g>
          <path
            d="M 810 470 L 810 380 Q 870 372 920 380 Q 990 392 1060 380 Q 1140 368 1220 380 Q 1300 392 1408 380 L 1408 470 Z"
            fill="url(#cm-ground)"
          />
          <path
            d="M 810 380 Q 880 370 950 378 Q 1030 388 1100 378 Q 1180 368 1260 378 Q 1340 386 1408 378 L 1408 386 Q 1340 392 1260 384 Q 1180 376 1100 386 Q 1030 394 950 386 Q 880 378 810 388 Z"
            fill="#5a8a3a"
            opacity=".75"
          />
          <ellipse cx="1080" cy="420" rx="60" ry="14" fill="#1f2a1e" />
        </g>

        {/* rope + axe (swinging trap) */}
        <g className="cm-axe">
          <line x1="980" y1="60" x2="980" y2="290" stroke="#8b6a36" strokeWidth="3" />
          <g transform="translate(980 290)">
            <rect x="-4" y="0" width="8" height="44" fill="#5a3a18" />
            <path d="M -4 0 q -24 -14 -36 8 q 24 8 36 -4 z" fill="#cfd4dc" stroke="#6a7080" strokeWidth="1.2" />
            <path d="M 4 0 q 24 -14 36 8 q -24 8 -36 -4 z" fill="#cfd4dc" stroke="#6a7080" strokeWidth="1.2" />
          </g>
        </g>

        {/* hero (Alaric) — реагирует на запуск кода: cast / win / hurt */}
        <g
          className={`cm-hero${
            phase === "casting"
              ? " cm-cast"
              : phase === "victory"
              ? " cm-win"
              : phase === "defeat"
              ? " cm-hurt"
              : ""
          }`}
          transform="translate(300 290)"
        >
          <ellipse cx="20" cy="110" rx="34" ry="6" fill="#000" opacity=".45" />
          <rect x="6" y="78" width="12" height="22" fill="#3a2814" />
          <rect x="22" y="78" width="12" height="22" fill="#3a2814" />
          <rect x="4" y="98" width="16" height="6" fill="#1a0e06" />
          <rect x="20" y="98" width="16" height="6" fill="#1a0e06" />
          <rect x="2" y="40" width="36" height="40" fill="#b6bccd" />
          <rect x="2" y="40" width="36" height="8" fill="#dfe4f0" />
          <rect x="2" y="70" width="36" height="6" fill="#7a8090" />
          <rect x="2" y="76" width="36" height="6" fill="#5a3a18" />
          <rect x="8" y="14" width="24" height="26" fill="#f0c79a" />
          <rect x="6" y="8" width="28" height="12" fill="#a93b1a" />
          <rect x="4" y="14" width="6" height="14" fill="#a93b1a" />
          <rect x="30" y="14" width="6" height="14" fill="#a93b1a" />
          <rect x="22" y="24" width="4" height="4" fill="#1a1a1a" />
          <g transform="translate(-12 44)">
            <path d="M 0 0 h 18 v 22 q -9 8 -18 0 z" fill="#8a5a2a" stroke="#3a2410" strokeWidth="1.4" />
            <path d="M 4 4 h 10 v 12 q -5 4 -10 0 z" fill="#caa05a" />
          </g>
          <g transform="translate(34 50)">
            <rect x="0" y="0" width="6" height="10" fill="#3a2410" />
            <rect x="-2" y="10" width="10" height="3" fill="#caa05a" />
            <polygon points="3,12 0,50 6,50" fill="#e6ebf2" stroke="#7a8090" strokeWidth="1" />
          </g>
          {/* заряд заклинания у руки — горит, пока выполняется код игрока */}
          {phase === "casting" && (
            <g transform="translate(42 50)">
              <g className="cm-charge">
                <circle r="8" fill="url(#cm-golemGlow)" />
                <circle r="3" fill="#ffe9a8" />
                <circle r="1.3" fill="#fffaf0" />
              </g>
            </g>
          )}
        </g>

        {/* golem — вздрагивает при успехе игрока, наступает при его ошибке */}
        <g
          transform="translate(470 270)"
          className={`cm-golem${
            phase === "victory"
              ? " cm-golem-hit"
              : phase === "defeat"
              ? " cm-golem-roar"
              : ""
          }`}
        >
          <circle cx="42" cy="60" r="80" fill="url(#cm-golemGlow)" className="cm-golem-glow" />
          <ellipse cx="42" cy="128" rx="40" ry="7" fill="#000" opacity=".45" />
          <rect x="10" y="40" width="64" height="60" fill="#9c7a3a" />
          <rect x="10" y="40" width="64" height="10" fill="#caa44a" />
          <rect x="10" y="92" width="64" height="8" fill="#6a4a1c" />
          <rect x="-8" y="46" width="20" height="40" fill="#9c7a3a" />
          <rect x="74" y="46" width="20" height="40" fill="#9c7a3a" />
          <rect x="-12" y="80" width="24" height="20" fill="#7a5a1c" />
          <rect x="74" y="80" width="24" height="20" fill="#7a5a1c" />
          <rect x="18" y="100" width="20" height="28" fill="#7a5a1c" />
          <rect x="46" y="100" width="20" height="28" fill="#7a5a1c" />
          <rect x="22" y="14" width="40" height="30" fill="#9c7a3a" />
          <rect x="20" y="10" width="44" height="6" fill="#caa44a" />
          <rect x="28" y="24" width="6" height="6" fill="#ffe066" className="cm-golem-eye" />
          <rect x="50" y="24" width="6" height="6" fill="#ffe066" className="cm-golem-eye" />
          <path d="M 24 50 l 8 14 l -4 14" stroke="#5a3a14" strokeWidth="1.5" fill="none" />
          <path d="M 56 56 l -6 18" stroke="#5a3a14" strokeWidth="1.5" fill="none" />
        </g>

        {/* успех: снаряд героя летит в голема + вспышка попадания */}
        {phase === "victory" && (
          <g key={`hit-${tick}`}>
            <g transform="translate(338 340)">
              <g className="cm-bolt">
                <circle r="7" fill="url(#cm-golemGlow)" />
                <circle r="3" fill="#ffe9a8" />
                <circle r="1.3" fill="#fffaf0" />
              </g>
            </g>
            <g
              className="cm-impact"
              style={{ animationDelay: "0.42s" }}
              transform="translate(510 334)"
            >
              <circle r="20" fill="none" stroke="#ffe9a8" strokeWidth="3" />
            </g>
          </g>
        )}

        {/* ошибка: заклинание срывается у руки героя */}
        {phase === "defeat" && (
          <g
            key={`fizz-${tick}`}
            className="cm-impact"
            transform="translate(338 340)"
          >
            <circle r="12" fill="none" stroke="#9aa3b2" strokeWidth="2.5" />
          </g>
        )}
      </svg>

      {/* нижний фейд — мягкий стык с тёмным доком страницы */}
      <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[#0a1322] to-transparent pointer-events-none" />

      {/* ── HUD: портрет + полоски HP/MP ────────────────────────── */}
      <div className="absolute top-3 left-3 sm:top-4 sm:left-4 flex items-center gap-3 bg-black/45 backdrop-blur-sm px-2.5 py-2 rounded-xl border border-white/10">
        <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-lg border-2 border-[#d9a441] overflow-hidden shadow-[0_0_14px_rgba(217,164,65,0.35)] shrink-0">
          <svg viewBox="0 0 60 60" className="w-full h-full">
            <rect width="60" height="60" fill="#241510" />
            <rect x="14" y="10" width="32" height="14" fill="#a93b1a" />
            <rect x="16" y="18" width="28" height="24" fill="#f0c79a" />
            <rect x="34" y="28" width="4" height="4" fill="#1a1a1a" />
            <rect x="10" y="42" width="40" height="16" fill="#b6bccd" />
            <rect x="10" y="42" width="40" height="4" fill="#dfe4f0" />
          </svg>
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5">
            <Heart size={12} className="text-[#ff5c5c] shrink-0" fill="#ff5c5c" />
            <div className="w-24 sm:w-32 h-2.5 rounded-md bg-[#1d2336] border border-black/40 overflow-hidden shadow-[inset_0_1px_2px_rgba(0,0,0,0.6)]">
              <div
                className="h-full rounded-md bg-gradient-to-b from-[#ff8585] to-[#c9252a] transition-[width] duration-500"
                style={{ width: `${hp}%` }}
              />
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Droplet size={12} className="text-[#5cb6ff] shrink-0" fill="#5cb6ff" />
            <div className="w-24 sm:w-32 h-2.5 rounded-md bg-[#1d2336] border border-black/40 overflow-hidden shadow-[inset_0_1px_2px_rgba(0,0,0,0.6)]">
              <div
                className="h-full rounded-md bg-gradient-to-b from-[#8ccaff] to-[#2a72c9] transition-[width] duration-500"
                style={{ width: `${mp}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Level-пилюля ────────────────────────────────────────── */}
      <div className="absolute top-3 sm:top-4 left-1/2 -translate-x-1/2 px-4 sm:px-5 py-1.5 rounded-lg bg-gradient-to-b from-[#1a2238] to-[#0c1224] border border-[#2c3a5d] text-[#e6e8f0] text-[11px] sm:text-xs font-bold tracking-[0.2em] uppercase shadow-[0_6px_14px_rgba(0,0,0,0.4)]">
        Level {level}
      </div>

      {/* idle-анимации сцены — чистый CSS, без библиотек */}
      <style jsx>{`
        .cm-stars circle {
          animation: cm-twinkle 3.4s ease-in-out infinite;
        }
        .cm-stars circle:nth-child(2n) { animation-delay: 1.1s; }
        .cm-stars circle:nth-child(3n) { animation-delay: 2.2s; }
        @keyframes cm-twinkle {
          0%, 100% { opacity: 0.85; }
          50% { opacity: 0.25; }
        }
        .cm-axe {
          transform-box: view-box;
          transform-origin: 980px 60px;
          animation: cm-swing 3.6s ease-in-out infinite;
        }
        @keyframes cm-swing {
          0%, 100% { transform: rotate(-7deg); }
          50% { transform: rotate(7deg); }
        }
        .cm-hero {
          transform-box: view-box;
          animation: cm-bob 2.4s ease-in-out infinite;
        }
        @keyframes cm-bob {
          0%, 100% { transform: translate(300px, 290px); }
          50% { transform: translate(300px, 281px); }
        }
        /* ── боевые реакции, завязанные на запуск кода игроком ── */
        .cm-hero.cm-cast { animation: cm-cast 0.7s ease-in-out infinite; }
        @keyframes cm-cast {
          0%, 100% { transform: translate(300px, 288px); }
          50% { transform: translate(305px, 285px); }
        }
        .cm-hero.cm-win { animation: cm-win 1s ease; }
        @keyframes cm-win {
          0% { transform: translate(300px, 290px); }
          25% { transform: translate(300px, 273px); }
          45% { transform: translate(300px, 284px); }
          68% { transform: translate(300px, 278px); }
          100% { transform: translate(300px, 290px); }
        }
        .cm-hero.cm-hurt { animation: cm-hurt 0.7s ease; }
        @keyframes cm-hurt {
          0% { transform: translate(300px, 290px); }
          20% { transform: translate(288px, 291px); }
          45% { transform: translate(303px, 289px); }
          70% { transform: translate(298px, 290px); }
          100% { transform: translate(300px, 290px); }
        }
        .cm-charge {
          transform-box: fill-box;
          transform-origin: center;
          animation: cm-charge 0.7s ease-in-out infinite;
        }
        @keyframes cm-charge {
          0%, 100% { transform: scale(0.7); opacity: 0.5; }
          50% { transform: scale(1.25); opacity: 1; }
        }
        .cm-bolt {
          transform-box: fill-box;
          animation: cm-bolt 0.5s ease-in both;
        }
        @keyframes cm-bolt {
          0% { transform: translate(0, 0) scale(0.7); opacity: 0; }
          20% { opacity: 1; }
          85% { opacity: 1; }
          100% { transform: translate(172px, -2px) scale(0.6); opacity: 0; }
        }
        .cm-impact {
          transform-box: fill-box;
          transform-origin: center;
          animation: cm-impact 0.55s ease-out both;
        }
        @keyframes cm-impact {
          0% { transform: scale(0.2); opacity: 0.9; }
          100% { transform: scale(2); opacity: 0; }
        }
        .cm-golem { transform-box: view-box; }
        .cm-golem.cm-golem-hit { animation: cm-golem-hit 0.85s ease; }
        @keyframes cm-golem-hit {
          0%, 45%, 100% { transform: translate(470px, 270px); }
          55% { transform: translate(479px, 272px); }
          67% { transform: translate(463px, 270px); }
          79% { transform: translate(476px, 271px); }
          90% { transform: translate(467px, 270px); }
        }
        .cm-golem.cm-golem-roar { animation: cm-golem-roar 0.7s ease; }
        @keyframes cm-golem-roar {
          0%, 100% { transform: translate(470px, 270px); }
          35% { transform: translate(452px, 265px); }
          55% { transform: translate(458px, 267px); }
        }
        .cm-golem-glow {
          animation: cm-glow 4s ease-in-out infinite;
          transform-origin: center;
        }
        @keyframes cm-glow {
          0%, 100% { opacity: 0.55; }
          50% { opacity: 1; }
        }
        .cm-golem-eye {
          animation: cm-eye 2.2s steps(1) infinite;
        }
        @keyframes cm-eye {
          0%, 90%, 100% { opacity: 1; }
          95% { opacity: 0.2; }
        }
        @media (prefers-reduced-motion: reduce) {
          .cm-stars circle,
          .cm-axe,
          .cm-hero,
          .cm-hero.cm-cast,
          .cm-hero.cm-win,
          .cm-hero.cm-hurt,
          .cm-charge,
          .cm-bolt,
          .cm-impact,
          .cm-golem-glow,
          .cm-golem-eye,
          .cm-golem.cm-golem-hit,
          .cm-golem.cm-golem-roar {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
