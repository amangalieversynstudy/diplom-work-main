import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Heart, Droplet } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { HERO_X_MIN, SCENE_HEIGHT, SCENE_WIDTH, stageView } from "../lib/stage";

// на сервере useLayoutEffect не нужен, в браузере он ставит рамку сцены до первой отрисовки
const useIsoLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

// Где снаряд героя встречает врага и куда он летит от руки героя (координаты сцены)
const BOLT_FROM_DX = 38;
const IMPACT_X = 486;

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
 *   hpPct   — здоровье героя, 0..100 (падает на 10 % за неудачу, не ниже 50 %)
 *   mpPct   — энергия попыток, 0..100 (только картинка, ничего не блокирует)
 *   heroX   — где стоит герой по X в координатах сцены (растёт вместе с шагами миссии)
 *   enemyHpPct — здоровье врага, 0..100 (100 минус доля решённых шагов)
 *   enemyHue   — сдвиг оттенка голема в градусах: у каждой миссии свой противник
 *   defeated   — враг повержен и больше не возвращается, пока страница открыта
 *   phase   — idle | casting | victory | defeat | finale (finale: последний удар и падение врага)
 *   heroName — имя героя (для aria/подписи), по умолчанию "Alaric"
 */
export default function CodemancerStage({
  level = 1,
  hpPct = 100,
  mpPct = 100,
  heroX = HERO_X_MIN,
  enemyHpPct = 100,
  enemyHue = 0,
  defeated = false,
  heroName = "Alaric",
  phase = "idle", // idle | casting | victory | defeat | finale — реакция на запуск кода
  tick = 0, // меняется на каждое событие, перезапускает one-shot анимации
}) {
  const { t } = useI18n();
  const clamp = (n) => Math.max(0, Math.min(100, Number(n) || 0));
  const hp = clamp(hpPct);
  const mp = clamp(mpPct);
  const enemyHp = clamp(enemyHpPct);
  const x = Number.isFinite(Number(heroX)) ? Number(heroX) : HERO_X_MIN;
  const boltDx = IMPACT_X - (x + BOLT_FROM_DX);

  // Рамка сцены (viewBox) считается по размеру блока: на широком и низком экране голем целиком
  // и полоска его HP остаются в кадре, а HUD и плашка уровня не закрывают героя и врага.
  const rootRef = useRef(null);
  const hudRef = useRef(null);
  const [view, setView] = useState(null);
  const [pxScale, setPxScale] = useState(0.55); // экранных пикселей в одной единице сцены
  useIsoLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const measure = () => {
      const hud = hudRef.current;
      const hudRight = hud ? hud.offsetLeft + hud.offsetWidth : 0;
      const next = stageView(root.clientWidth, root.clientHeight, hudRight);
      setView(next);
      if (next.w > 0 && root.clientWidth > 0) setPxScale(root.clientWidth / next.w);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  // Герой идёт при смене шага: короткое покачивание «шагами», потом покой.
  // Сам сдвиг делает CSS-переход, здесь только метка на время ходьбы.
  const [walking, setWalking] = useState(false);
  const lastXRef = useRef(x);
  useEffect(() => {
    if (lastXRef.current === x) return undefined;
    lastXRef.current = x;
    setWalking(true);
    const timer = setTimeout(() => setWalking(false), 720);
    return () => clearTimeout(timer);
  }, [x]);

  // idle-циклы (звёзды, топор, свечение, глаза) засыпают через ~4 с после
  // последнего события сцены и пока вкладка скрыта; дыхание героя и окно остаются
  const [calm, setCalm] = useState(false);
  useEffect(() => {
    let timer;
    const arm = () => {
      clearTimeout(timer);
      timer = setTimeout(() => setCalm(true), 4000);
    };
    const onVisibility = () => {
      if (document.hidden) {
        clearTimeout(timer);
        setCalm(true);
      } else {
        setCalm(false);
        arm();
      }
    };
    if (document.hidden) {
      setCalm(true);
    } else {
      setCalm(false);
      arm();
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [tick, phase, x, enemyHp]);

  return (
    <div
      ref={rootRef}
      className={`codemancer-stage relative w-full shrink-0 h-40 md:h-44 xl:h-[clamp(112px,18vh,224px)] overflow-hidden border-b border-border bg-[#0a1322] select-none ${phase !== "idle" ? "cm-" + phase : ""} ${calm ? "cm-calm" : ""}`}
      role="img"
      aria-label={`${heroName}, level ${level}`}
    >
      {/* ── Пиксель-арт сцена (SVG) ─────────────────────────────── */}
      <svg
        viewBox={view ? `${view.x} ${view.y} ${view.w} ${view.h}` : `0 0 ${SCENE_WIDTH} ${SCENE_HEIGHT}`}
        preserveAspectRatio={view ? "xMinYMin slice" : "xMidYMax slice"}
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
        <rect x="-2600" y="-500" width="6600" height="970" fill="url(#cm-sky)" />
        {/* тинт всей сцены — реакция окружения на исход задания */}
        <rect className="cm-tint" x="-2600" y="-500" width="6600" height="970" fill="#000" opacity="0" />

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
          <circle r="60" fill="url(#cm-moonGlow)" className="cm-moonlight" />
          <path d="M -14 -22 a 22 22 0 1 0 0 44 a 17 17 0 1 1 0 -44 z" fill="#f7efcc" />
        </g>

        {/* distant mountains */}
        <path
          d="M 0 240 L 120 180 L 220 220 L 340 150 L 480 220 L 560 180 L 700 240 L 820 200 L 980 240 L 1100 180 L 1240 230 L 1408 200 L 1408 320 L 0 320 Z"
          fill="url(#cm-mountains)"
          opacity=".75"
        />
        {/* продолжение гор и земли за краями сцены: на широком экране кадр шире 1408 */}
        <rect x="-2600" y="232" width="2600" height="88" fill="url(#cm-mountains)" opacity=".75" />
        <rect x="1408" y="210" width="2600" height="110" fill="url(#cm-mountains)" opacity=".75" />

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
          <rect x="35" y="100" width="14" height="20" fill="#ffd86a" opacity=".7" className="cm-window" />
          <rect x="175" y="100" width="14" height="20" fill="#ffd86a" opacity=".7" className="cm-window" />
          <rect x="100" y="130" width="14" height="20" fill="#ffd86a" opacity=".7" className="cm-window" />
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

        <rect x="-2600" y="362" width="2600" height="108" fill="url(#cm-ground)" />
        <rect x="-2600" y="356" width="2600" height="8" fill="#5a8a3a" opacity=".75" />
        <rect x="1407" y="380" width="2600" height="90" fill="url(#cm-ground)" />
        <rect x="1407" y="376" width="2600" height="8" fill="#5a8a3a" opacity=".75" />

        {/* spikes pit */}
        <g transform="translate(620 320)" className="cm-spikes">
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

        {/* hero (Alaric): внешняя группа ведёт его вперёд по ходу миссии, внутренняя
            реагирует на запуск кода: cast / win / hurt (отскок за щитом) / шаги */}
        <g className="cm-hero-pos" style={{ transform: `translate(${x}px, 290px)` }}>
        <g
          className={`cm-hero${
            walking
              ? " cm-walking"
              : phase === "casting"
              ? " cm-cast"
              : phase === "victory" || phase === "finale"
              ? " cm-strike"
              : phase === "defeat"
              ? " cm-hurt"
              : ""
          }`}
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
            <g className={`cm-shield${phase === "defeat" ? " cm-shield-up" : ""}`}>
              <path d="M 0 0 h 18 v 22 q -9 8 -18 0 z" fill="#8a5a2a" stroke="#3a2410" strokeWidth="1.4" />
              <path d="M 4 4 h 10 v 12 q -5 4 -10 0 z" fill="#caa05a" />
            </g>
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
        </g>

        {/* golem — вздрагивает при успехе игрока, наступает при его ошибке, рассыпается в финале */}
        <g transform="translate(470 270)" style={enemyHue ? { filter: `hue-rotate(${enemyHue}deg)` } : undefined}>
        <g
          className={`cm-golem${
            phase === "finale"
              ? " cm-golem-fall"
              : defeated
              ? " cm-golem-down"
              : phase === "victory"
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
        {/* обломки на месте поверженного врага: проступают, пока голем оседает */}
        {defeated && (
          <g className={`cm-rubble${phase === "finale" ? " cm-rubble-in" : ""}`} stroke="#6a4a1c" strokeWidth="2">
            <rect x="-14" y="106" width="34" height="22" fill="#9c7a3a" />
            <rect x="-14" y="106" width="34" height="6" fill="#caa44a" stroke="none" />
            <rect x="18" y="88" width="32" height="40" fill="#caa44a" />
            <rect x="18" y="88" width="32" height="8" fill="#e0c06a" stroke="none" />
            <rect x="48" y="100" width="36" height="28" fill="#9c7a3a" />
            <rect x="48" y="100" width="36" height="6" fill="#caa44a" stroke="none" />
            <rect x="80" y="110" width="26" height="18" fill="#caa44a" />
            <rect x="34" y="120" width="24" height="8" fill="#7a5a1c" />
            <rect x="26" y="74" width="12" height="12" fill="#ffe066" stroke="none" />
          </g>
        )}
        </g>

        {/* здоровье врага: полоска над головой, меняется только масштабом */}
        {(!defeated || phase === "finale") && (
          <g transform="translate(452 244)">
            <g className={phase === "finale" ? "cm-enemy-bar-out" : undefined}>
            {/* имя голема держим читаемым (11 экранных px) при любом масштабе сцены */}
            <text
              x="60"
              y={-3 / pxScale}
              textAnchor="middle"
              fontSize={11 / pxScale}
              fontWeight="700"
              fill="#cfd6f0"
              stroke="#0a1322"
              strokeWidth={3 / pxScale}
              strokeLinejoin="round"
              paintOrder="stroke"
            >
              {t(`stage.bosses.${Math.abs(Math.round(enemyHue / 30)) % 4}`)}
            </text>
            <rect width="120" height="14" rx="4" fill="#1d2336" stroke="#000" strokeOpacity=".4" />
            <rect x="2" y="2" width="116" height="10" rx="3" fill="#c9252a" className="cm-enemy-hp" style={{ transform: `scaleX(${enemyHp / 100})` }} />
            </g>
          </g>
        )}

        {/* успех: снаряд героя летит в голема + вспышка попадания (в финале это последний удар) */}
        {(phase === "victory" || phase === "finale") && (
          <g key={`hit-${tick}`}>
            <g transform={`translate(${x + BOLT_FROM_DX} 340)`}>
              <g className="cm-bolt" style={{ "--bolt-dx": `${boltDx}px` }}>
                <circle r="28" fill="url(#cm-golemGlow)" />
                <circle r="10" fill="#ffe9a8" />
                <circle r="4.5" fill="#fffaf0" />
              </g>
              <g className="cm-impact" style={{ animationDuration: "0.35s" }}>
                <circle r="14" fill="none" stroke="#ffe9a8" strokeWidth="3" />
              </g>
            </g>
            <g
              className="cm-impact"
              style={{ animationDelay: "0.4s" }}
              transform={`translate(${IMPACT_X} 334)`}
            >
              <circle r="20" fill="#ffe9a8" fillOpacity=".3" stroke="#ffe9a8" strokeWidth="4" />
            </g>
          </g>
        )}

        {/* ошибка: удар врага гаснет о щит героя (искра у щита, без вспышек на весь экран) */}
        {phase === "defeat" && (
          <g
            key={`block-${tick}`}
            className="cm-impact"
            style={{ animationDelay: "0.2s" }}
            transform={`translate(${x - 6} 350)`}
          >
            <circle r="14" fill="none" stroke="#cfd6f0" strokeWidth="2.5" />
          </g>
        )}
      </svg>

      {/* нижний фейд — мягкий стык с тёмным доком страницы */}
      <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[#0a1322] to-transparent pointer-events-none" />

      {/* ── HUD: портрет + полоски HP/MP ────────────────────────── */}
      <div ref={hudRef} className="absolute top-3 left-3 sm:top-4 sm:left-4 flex items-center gap-3 bg-black/45 backdrop-blur-sm px-2.5 py-1.5 sm:py-2 rounded-xl border border-white/10">
        <div className="hidden sm:block w-11 h-11 sm:w-14 sm:h-14 rounded-lg border-2 border-[#d9a441] overflow-hidden shadow-[0_0_14px_rgba(217,164,65,0.35)] shrink-0">
          <svg viewBox="0 0 60 60" className="w-full h-full">
            <rect width="60" height="60" fill="#241510" />
            <rect x="14" y="10" width="32" height="14" fill="#a93b1a" />
            <rect x="16" y="18" width="28" height="24" fill="#f0c79a" />
            <rect x="34" y="28" width="4" height="4" fill="#1a1a1a" />
            <rect x="10" y="42" width="40" height="16" fill="#b6bccd" />
            <rect x="10" y="42" width="40" height="4" fill="#dfe4f0" />
          </svg>
        </div>
        <div className="flex flex-row sm:flex-col gap-3 sm:gap-1.5">
          <div className="flex items-center gap-1.5" title={t("stage.hp")}>
            <Heart size={12} className="text-[#ff5c5c] shrink-0" fill="#ff5c5c" />
            <div className="w-14 sm:w-32 h-2.5 rounded-md bg-[#1d2336] border border-black/40 overflow-hidden shadow-[inset_0_1px_2px_rgba(0,0,0,0.6)]">
              <div
                className="h-full w-full origin-left bg-gradient-to-b from-[#ff8585] to-[#c9252a] transition-transform duration-500"
                style={{ transform: `scaleX(${hp / 100})` }}
              />
            </div>
          </div>
          <div className="flex items-center gap-1.5" title={t("stage.mp")}>
            <Droplet size={12} className="text-[#5cb6ff] shrink-0" fill="#5cb6ff" />
            <div className="w-14 sm:w-32 h-2.5 rounded-md bg-[#1d2336] border border-black/40 overflow-hidden shadow-[inset_0_1px_2px_rgba(0,0,0,0.6)]">
              <div
                className="h-full w-full origin-left bg-gradient-to-b from-[#8ccaff] to-[#2a72c9] transition-transform duration-500"
                style={{ transform: `scaleX(${mp / 100})` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Level-пилюля ────────────────────────────────────────── */}
      <div className="absolute top-3 sm:top-4 right-3 sm:right-auto sm:left-1/2 sm:-translate-x-1/2 px-2.5 sm:px-5 py-1 sm:py-1.5 rounded-lg bg-gradient-to-b from-[#1a2238] to-[#0c1224] border border-[#2c3a5d] text-[#e6e8f0] text-xs sm:text-xs font-bold tracking-[0.12em] sm:tracking-[0.2em] uppercase shadow-[0_6px_14px_rgba(0,0,0,0.4)]">
        {t("stage.level").replace("{n}", level)}
      </div>

      {/* idle-анимации сцены — чистый CSS, без библиотек */}
      <style jsx>{`
        .cm-stars circle {
          animation: cm-twinkle 3.4s ease-in-out infinite;
        }
        .cm-calm .cm-stars circle,
        .cm-calm .cm-axe,
        .cm-calm .cm-golem-glow,
        .cm-calm .cm-golem-eye {
          animation-play-state: paused;
        }
        .cm-stars circle:nth-child(2n) { animation-delay: 1.1s; }
        .cm-stars circle:nth-child(3n) { animation-delay: 2.2s; }
        @keyframes cm-twinkle {
          0%, 100% { opacity: 0.85; }
          50% { opacity: 0.25; }
        }
        .cm-axe {
          transform-box: fill-box;
          transform-origin: 50% 0%;
          animation: cm-swing 3.6s ease-in-out infinite;
        }
        @keyframes cm-swing {
          0%, 100% { transform: rotate(-7deg); }
          50% { transform: rotate(7deg); }
        }
        /* внешняя группа ведёт героя по сцене, внутренняя только качается на месте */
        .cm-hero-pos {
          transform-box: view-box;
          transition: transform 0.7s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .cm-hero {
          animation: cm-bob 2.4s ease-in-out infinite;
        }
        @keyframes cm-bob {
          0%, 100% { transform: translate(0, 0); }
          50% { transform: translate(0, -9px); }
        }
        /* ходьба между шагами: 3 кадра покачивания «шагами» за время перехода */
        .cm-hero.cm-walking { animation: cm-walk 0.7s steps(1, end) both; }
        @keyframes cm-walk {
          0% { transform: translate(0, 0); }
          17% { transform: translate(0, -5px); }
          33% { transform: translate(0, 0); }
          50% { transform: translate(0, -5px); }
          67% { transform: translate(0, 0); }
          83% { transform: translate(0, -5px); }
          100% { transform: translate(0, 0); }
        }
        /* ── боевые реакции, завязанные на запуск кода игроком ── */
        .cm-hero.cm-cast { animation: cm-cast 0.7s ease-in-out infinite; }
        @keyframes cm-cast {
          0%, 100% { transform: translate(0, -2px); }
          50% { transform: translate(5px, -5px); }
        }
        /* удар: замах назад, выпад вперёд (снаряд уходит), потом победный подскок */
        .cm-hero.cm-strike { animation: cm-strike 1.1s ease; }
        @keyframes cm-strike {
          0% { transform: translate(0, 0); }
          10% { transform: translate(-9px, 1px); }
          22% { transform: translate(18px, -3px); }
          40% { transform: translate(18px, -3px); }
          52% { transform: translate(0, 0); }
          68% { transform: translate(0, -16px); }
          84% { transform: translate(0, -5px); }
          100% { transform: translate(0, 0); }
        }
        /* отскок за щитом: удар врага отбрасывает героя на несколько пикселей назад */
        .cm-hero.cm-hurt { animation: cm-hurt 0.8s ease; }
        @keyframes cm-hurt {
          0%, 30% { transform: translate(0, 0); }
          42% { transform: translate(-9px, 0); }
          62% { transform: translate(-3px, 0); }
          100% { transform: translate(0, 0); }
        }
        .cm-shield { transform-box: fill-box; transform-origin: center; }
        .cm-shield.cm-shield-up { animation: cm-shield-up 0.8s ease; }
        @keyframes cm-shield-up {
          0%, 25% { transform: translate(0, 0) scale(1); }
          40%, 70% { transform: translate(4px, -4px) scale(1.25); }
          100% { transform: translate(0, 0) scale(1); }
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
          0% { transform: translate(0, 0) scale(0.6); opacity: 0; }
          12% { transform: translate(0, 0) scale(1.2); opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translate(var(--bolt-dx, 172px), -2px) scale(0.9); opacity: 0; }
        }
        .cm-impact {
          transform-box: fill-box;
          transform-origin: center;
          animation: cm-impact 0.5s ease-out both;
        }
        @keyframes cm-impact {
          0% { transform: scale(0.2); opacity: 1; }
          100% { transform: scale(2.6); opacity: 0; }
        }
        .cm-golem { transform-box: fill-box; transform-origin: 50% 100%; }
        .cm-golem.cm-golem-hit { animation: cm-golem-hit 0.85s ease; }
        @keyframes cm-golem-hit {
          0%, 45%, 100% { transform: translate(0, 0); }
          52% { transform: translate(13px, 2px); }
          62% { transform: translate(-11px, 0); }
          72% { transform: translate(9px, 1px); }
          82% { transform: translate(-6px, 0); }
          92% { transform: translate(3px, 0); }
        }
        .cm-golem.cm-golem-roar { animation: cm-golem-roar 0.8s ease; }
        @keyframes cm-golem-roar {
          0%, 100% { transform: translate(0, 0); }
          35% { transform: translate(-18px, -5px); }
          55% { transform: translate(-12px, -3px); }
        }
        /* финал: последний удар, голем вздрагивает, оседает и рассыпается; в конце остаются обломки */
        .cm-golem.cm-golem-fall { animation: cm-golem-fall 1.5s ease-in both; }
        .cm-golem.cm-golem-down { transform: translate(0, 4px) scale(1, 0.12); opacity: 0; }
        @keyframes cm-golem-fall {
          0%, 26% { transform: translate(0, 0) scale(1, 1); opacity: 1; }
          31% { transform: translate(12px, 0) scale(1, 1); opacity: 1; }
          37% { transform: translate(-11px, 0) scale(1, 1); opacity: 1; }
          43% { transform: translate(9px, 0) scale(1, 0.99); opacity: 1; }
          49% { transform: translate(-6px, 0) scale(1, 0.98); opacity: 1; }
          54% { transform: translate(0, 0) scale(1, 0.95); opacity: 1; }
          100% { transform: translate(0, 4px) scale(1, 0.12); opacity: 0; }
        }
        .cm-rubble.cm-rubble-in { animation: cm-rubble-in 0.5s ease-out 1s both; }
        @keyframes cm-rubble-in { from { opacity: 0; } to { opacity: 1; } }
        .cm-enemy-hp {
          transform-box: fill-box;
          transform-origin: left center;
          transition: transform 0.4s ease 0.4s;
        }
        .cm-enemy-bar-out { animation: cm-bar-out 0.5s ease 0.8s both; }
        @keyframes cm-bar-out { from { opacity: 1; } to { opacity: 0; } }
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
        /* ── реакция ОКРУЖЕНИЯ на исход задания (не только герой/голем) ── */
        .cm-tint { transform-box: view-box; }
        .cm-victory .cm-tint,
        .cm-finale .cm-tint { fill: #d9a441; animation: cm-flash 0.9s ease; }
        @keyframes cm-flash { 0% { opacity: 0; } 25% { opacity: 0.18; } 100% { opacity: 0; } }

        .cm-victory .cm-window,
        .cm-finale .cm-window { animation: cm-win-flare 1s ease; }
        .cm-defeat .cm-window { opacity: 0.2; transition: opacity 0.4s ease; }
        .cm-casting .cm-window { animation: cm-flicker 1.1s ease-in-out infinite; }
        @keyframes cm-win-flare { 0%, 100% { opacity: 0.7; } 40% { opacity: 1; } }
        @keyframes cm-flicker { 0%, 100% { opacity: 0.7; } 50% { opacity: 0.35; } }

        .cm-moonlight { transform-box: fill-box; transform-origin: center; }
        .cm-victory .cm-moonlight,
        .cm-finale .cm-moonlight { animation: cm-moon-up 1s ease; }
        .cm-defeat .cm-moonlight { opacity: 0.3; transition: opacity 0.4s ease; }
        @keyframes cm-moon-up { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.35); } }

        .cm-victory .cm-stars circle { animation-duration: 1s; }
        .cm-defeat .cm-axe { animation-duration: 1.2s; }
        .cm-casting .cm-axe { animation-duration: 2.2s; }

        @media (prefers-reduced-motion: reduce) {
          .cm-stars circle,
          .cm-tint,
          .cm-window,
          .cm-moonlight,
          .cm-axe,
          .cm-hero,
          .cm-hero.cm-walking,
          .cm-hero.cm-cast,
          .cm-hero.cm-strike,
          .cm-hero.cm-hurt,
          .cm-shield.cm-shield-up,
          .cm-charge,
          .cm-golem-glow,
          .cm-golem-eye,
          .cm-golem.cm-golem-hit,
          .cm-golem.cm-golem-roar,
          .cm-golem.cm-golem-fall,
          .cm-rubble.cm-rubble-in,
          .cm-enemy-bar-out {
            animation: none;
          }
          /* без движения: позиции и полоски меняются сразу, снарядов и вспышек нет */
          .cm-hero-pos,
          .cm-enemy-hp {
            transition: none;
          }
          .cm-bolt,
          .cm-impact {
            display: none;
          }
          .cm-golem.cm-golem-fall { transform: translate(0, 4px) scale(1, 0.12); opacity: 0; }
          .cm-enemy-bar-out { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
