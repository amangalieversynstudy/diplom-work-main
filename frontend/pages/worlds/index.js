import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Layout from "../../components/Layout";
import { useDictionary } from "../../lib/i18n";
import { Lock, CheckCircle, X as XIcon, Compass } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Missions, missionStatus } from "../../lib/api";
import logger from "../../lib/logger";
import { useI18n } from "../../lib/i18n";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export default function Worlds() {
  const dict = useDictionary();
  const { language } = useI18n();
  const worldsDict = dict.worldsPage || {};
  
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const pinContainerRef = useRef(null);
  const mapScrollRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    Missions.list()
      .then((data) => {
        const items = Array.isArray(data) ? data : data?.results || [];
        setMissions(items);
      })
      .catch(logger.error)
      .finally(() => setLoading(false));
    // MID-06: refetch при смене языка
  }, [language]);

  // Вычисляем хаотичные координаты
  const getCoords = (index, total) => {
    const step = total > 1 ? 72 / (total - 1) : 0;
    const xVariations = [0, 4, -3, 5, -4, 2, -2, 3];
    let xVar = xVariations[index % xVariations.length];
    if (index === 0 || index === total - 1) xVar = 0;

    const yOffsets = [15, -25, 5, -30, 20, -10, 35, -20];
    return {
      x: 8 + index * step + xVar,
      y: 50 + yOffsets[index % yOffsets.length]
    };
  };

  // Генерируем линию
  const generatePath = (missionsArr) => {
    if (!missionsArr || missionsArr.length === 0) return "";
    const len = missionsArr.length;
    let path = `M ${getCoords(0, len).x} ${getCoords(0, len).y}`;
    
    const cp1YVars = [60, -55, 65, -50, 70, -60, 55, -65];
    const cp2YVars = [-60, 55, -65, 50, -70, 60, -55, 65];
    const cpXVars1 = [0.2, 0.25, 0.2, 0.3, 0.25, 0.2, 0.3, 0.25];
    const cpXVars2 = [0.8, 0.75, 0.8, 0.7, 0.75, 0.8, 0.7, 0.75];

    for (let i = 1; i < len; i++) {
      const prev = getCoords(i - 1, len);
      const curr = getCoords(i, len);
      const cp1X = prev.x + (curr.x - prev.x) * cpXVars1[i % cpXVars1.length];
      const cp1Y = prev.y + cp1YVars[i % cp1YVars.length];
      const cp2X = prev.x + (curr.x - prev.x) * cpXVars2[i % cpXVars2.length];
      const cp2Y = curr.y + cp2YVars[i % cp2YVars.length];
      path += ` C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${curr.x} ${curr.y}`;
    }
    return path;
  };

  // Перехват горизонтального жеста трекпада — РАБОТАЕТ ВСЕГДА
  useEffect(() => {
    if (loading) return; // ИСПРАВЛЕНО: убрана блокировка пустого списка миссий

    const container = pinContainerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        window.scrollTo({
          top: window.scrollY + e.deltaX,
          behavior: "auto"
        });
      }
    };

    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, [loading, missions]);

  // Инициализация ScrollTrigger — РАБОТАЕТ ВСЕГДА
  useGSAP(() => {
    if (loading) return; // ИСПРАВЛЕНО: убрана блокировка пустого списка миссий

    const tl = gsap.timeline();

    if (missions.length > 0) {
      tl.fromTo(".map-path", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 2.5, ease: "power2.inOut" });
      tl.fromTo(".mission-node", { scale: 0, opacity: 0, y: 20 }, { scale: 1, opacity: 1, y: 0, duration: 0.5, stagger: 0.1, ease: "back.out(1.5)" }, "-=2");
    }

    const mapEl = mapScrollRef.current;
    const moveDist = mapEl.scrollWidth - window.innerWidth + 48;

    if (moveDist > 0) {
      gsap.to(mapEl, {
        x: -moveDist,
        ease: "none",
        scrollTrigger: {
          trigger: pinContainerRef.current,
          pin: true,
          scrub: 1,
          start: "top top",
          end: () => `+=${moveDist}`,
          invalidateOnRefresh: true,
        }
      });

      ScrollTrigger.refresh();
    }
  }, { scope: pinContainerRef, dependencies: [loading, missions] });

  return (
    <Layout hideFooter noBottomPadding>
      <div className="max-w-7xl mx-auto px-6 pt-24 pb-4">
        {/* ── Заголовок ── */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase tracking-widest mb-4">
            <Compass size={16} />
            <span>{worldsDict.atlasTitle || "Атлас"}</span>
          </div>
          <h1 className="font-display text-4xl md:text-5xl lg:text-6xl font-bold text-text mb-6">
            Карта миров
          </h1>
          <p className="text-muted text-lg max-w-2xl leading-relaxed">
            Каждый архипелаг таит в себе знания и опасности. Следуйте по чернильным тропам, чтобы найти сокровища кода.
          </p>
        </div>
      </div>

      {/* ── Контейнер карты ── */}
      <div ref={pinContainerRef} className="w-full h-screen overflow-hidden flex flex-col justify-center bg-bg relative">
        
        {/* ИСПРАВЛЕНО: Оверлеи состояний теперь зафиксированы по центру экрана и не улетают при прокрутке */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-[#5c3a21] font-display text-2xl font-bold tracking-widest uppercase animate-pulse z-20 pointer-events-none">
            Разворачиваем пергамент...
          </div>
        )}

        {!loading && missions.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-[#5c3a21] font-display text-xl font-bold z-20 pointer-events-none">
            Пираты украли карту. Задания не найдены.
          </div>
        )}

        {/* Холст пергамента */}
        <div 
          ref={mapScrollRef} 
          className="relative h-[70vh] w-[300vw] sm:w-[250vw] md:w-[200vw] lg:w-[150vw] ml-6 mr-6 rounded-[2.5rem] border-8 border-[#5c3a21] bg-[#dcb98a] shadow-2xl shrink-0 overflow-hidden"
        >
          {/* Бумажная текстура */}
          <div className="absolute inset-0 pointer-events-none opacity-30 mix-blend-multiply rounded-[inherit]">
            <svg className="w-full h-full">
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
              backgroundImage: 'linear-gradient(#5c3a21 1.5px, transparent 1.5px), linear-gradient(90deg, #5c3a21 1.5px, transparent 1.5px)', 
              backgroundSize: '80px 80px' 
            }} 
          />
          
          <div className="absolute inset-0 shadow-[inset_0_0_150px_rgba(62,39,35,0.6)] pointer-events-none rounded-[inherit]" />

          {!loading && missions.length > 0 && (
            <>
              {/* SVG Путь */}
              <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none">
                <defs>
                  <mask id="path-mask">
                    <path
                      className="map-path"
                      d={generatePath(missions)}
                      fill="none"
                      stroke="white"
                      strokeWidth="16"
                      vectorEffect="non-scaling-stroke"
                      pathLength="100"
                      style={{ strokeDasharray: "100", strokeDashoffset: "100" }}
                    />
                  </mask>
                </defs>
                
                <path
                  d={generatePath(missions)}
                  fill="none"
                  stroke="#8b5a2b"
                  strokeWidth="3.5"
                  strokeDasharray="6,6"
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d={generatePath(missions)}
                  fill="none"
                  stroke="#8e1d1d"
                  strokeWidth="4.5"
                  strokeDasharray="6,6"
                  vectorEffect="non-scaling-stroke"
                  mask="url(#path-mask)"
                />
              </svg>

              {/* Узлы миссий */}
              {missions.map((mission, index) => {
                const coords = getCoords(index, missions.length);
                const statusVal = missionStatus(mission);
                const isCompleted = statusVal === "completed";
                const isLocked = statusVal === "locked";
                const isActive = statusVal === "available";
                const Icon = isCompleted ? CheckCircle : (isLocked ? Lock : XIcon);

                return (
                  <Link
                    href={isLocked ? "#" : `/missions/${mission.id}`}
                    key={mission.id}
                    onClick={(e) => isLocked && e.preventDefault()}
                    className={`mission-node absolute transform -translate-x-1/2 -translate-y-1/2 group z-10 ${isLocked ? 'cursor-default' : 'cursor-pointer'}`}
                    style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
                  >
                    {isActive && (
                      <span className="absolute inset-0 rounded-full bg-[#8e1d1d]/40 animate-ping group-hover:bg-[#8e1d1d]/60 transition-colors duration-300" style={{ zIndex: -1 }}></span>
                    )}

                    <div className={`flex items-center p-1 md:p-1.5 rounded-full border-2 transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] shadow-[0_4px_10px_rgba(62,39,35,0.4)] group-hover:scale-110
                      ${isLocked ? 'bg-[#c4a173] border-[#8b5a2b]' : 'bg-[#f4e4bc] border-[#8e1d1d] group-hover:bg-[#fff0d4] group-hover:shadow-[0_0_25px_rgba(142,29,29,0.5)]'}
                    `}>
                      <div className={`flex-shrink-0 w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full transition-all duration-500 shadow-inner group-hover:shadow-[inset_0_0_15px_rgba(0,0,0,0.4)]
                        ${isLocked ? 'text-[#8b5a2b] bg-transparent' : (isCompleted ? 'bg-[#2e633a] text-[#f4e4bc]' : 'bg-[#8e1d1d] text-[#f4e4bc]')}
                      `}>
                        <Icon size={isLocked ? 18 : 22} strokeWidth={isLocked ? 2 : 2.5} className="transition-transform duration-500 group-hover:scale-125 group-hover:rotate-12" />
                      </div>

                      <div className="max-w-0 overflow-hidden whitespace-nowrap opacity-0 group-hover:max-w-[200px] group-hover:opacity-100 group-hover:ml-3 group-hover:pr-4 transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]">
                        <p className={`text-sm font-display font-bold tracking-wide ${isLocked ? 'text-[#5c3a21]' : 'text-[#3e2723]'}`}>
                          {mission.title || mission.name || worldsDict.missionFallback || "Миссия"}
                        </p>
                        <p className={`text-[10px] font-bold uppercase tracking-widest mt-0.5 ${isLocked ? 'text-[#8b5a2b]' : 'text-[#8e1d1d]'}`}>
                          {mission.chapter || mission.tier || worldsDict.chapterFallback || "Глава"}
                        </p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}