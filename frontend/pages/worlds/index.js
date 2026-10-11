import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Layout from "../../components/Layout";
import MissionPath from "../../components/MissionPath";
import { toast } from "sonner";
import { useDictionary } from "../../lib/i18n";
import { lockReason, missionTitle, missionXp } from "../../lib/missions";
import { Lock, CheckCircle, X as XIcon, Compass } from "lucide-react";
import gsap from "gsap";
import { prefersReducedMotion } from "../../lib/motion";
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
  const { t, language } = useI18n();
  const worldsDict = dict.worldsPage || {};
  
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [heroArrived, setHeroArrived] = useState(false);
  
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
    // refetch при смене языка
  }, [language]);

  // Маркер героя «доезжает» к текущему узлу при открытии карты.
  useEffect(() => {
    if (loading || missions.length === 0) return undefined;
    setHeroArrived(false);
    const id = setTimeout(() => setHeroArrived(true), 500);
    return () => clearTimeout(id);
  }, [loading, missions]);

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
    if (!container || prefersReducedMotion()) return;

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
      tl.fromTo(".mission-node", { scale: 0.85, opacity: 0, y: 12 }, { scale: 1, opacity: 1, y: 0, duration: 0.4, stagger: 0.06, ease: "back.out(1.5)" }, "-=2");
    }

    const mapEl = mapScrollRef.current;
    const moveDist = mapEl.scrollWidth - window.innerWidth + 48;

    // при reduced-motion без пина: обычная горизонтальная прокрутка (см. onWheel выше)
    if (moveDist > 0 && !prefersReducedMotion()) {
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
    } else if (moveDist > 0) {
      pinContainerRef.current.style.overflowX = "auto"; // без пина: карта прокручивается по горизонтали
    }
  }, { scope: pinContainerRef, dependencies: [loading, missions] });

  // Первая доступная миссия: её подсвечиваем, и к ней ведёт полоса «Продолжить» над картой.
  const current = missions.find((m) => missionStatus(m) === "available") || null;

  // Текущий узел = первый доступный, иначе последний пройденный.
  const heroTarget = (() => {
    if (!missions.length) return 0;
    const avail = missions.findIndex((m) => missionStatus(m) === "available");
    if (avail !== -1) return avail;
    let lastDone = 0;
    missions.forEach((m, i) => {
      if (missionStatus(m) === "completed") lastDone = i;
    });
    return lastDone;
  })();
  const heroCoords = getCoords(
    heroArrived ? heroTarget : Math.max(0, heroTarget - 1),
    missions.length
  );

  return (
    <Layout hideFooter noBottomPadding>
      <div className="max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 pt-24 pb-4">
        {/* ── Заголовок ── */}
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase tracking-widest mb-3">
            <Compass size={16} />
            <span>{worldsDict.atlasTitle || "Атлас"}</span>
          </div>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-text mb-4">
            {worldsDict.mapTitle || "Карта миров"}
          </h1>
          <p className="text-muted text-base md:text-lg max-w-2xl leading-relaxed">
            {worldsDict.mapSubtitle ||
              "Каждый архипелаг таит в себе знания и опасности. Следуй по чернильным тропам, чтобы найти сокровища кода."}
          </p>
        </div>

        {current ? (
          <div className="hidden lg:flex items-center justify-between gap-4 rounded-2xl border border-primary/30 bg-primary/10 px-6 py-4">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-widest text-primary">
                {t(current.user_progress?.status === "in_progress" ? "worldsPage.mobile.continue" : "worldsPage.mobile.start")}
              </p>
              <p className="mt-1 truncate font-display text-xl font-bold text-text">
                {missionTitle(current, language, worldsDict.missionFallback || "Миссия")}
              </p>
              <p className="mt-0.5 text-sm text-muted">
                {t("worldsPage.mobile.reward").replace("{xp}", missionXp(current))}
                {(current.tasks || []).length
                  ? ` · ${t("worldsPage.mobile.steps").replace("{n}", (current.tasks || []).length)}`
                  : ""}
              </p>
            </div>
            <Link
              href={`/missions/${current.id}`}
              className="inline-flex min-h-[48px] shrink-0 items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 font-semibold text-on-primary shadow-glow transition hover:-translate-y-0.5 hover:bg-primary-dk"
            >
              {t(current.user_progress?.status === "in_progress" ? "worldsPage.mobile.continue" : "worldsPage.mobile.start")}
            </Link>
          </div>
        ) : null}
      </div>

      {/* ── Контейнер карты ── */}
      <div ref={pinContainerRef} className="hidden lg:flex w-full h-screen overflow-hidden flex-col justify-center bg-bg relative">
        
        {/* ИСПРАВЛЕНО: Оверлеи состояний теперь зафиксированы по центру экрана и не улетают при прокрутке */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-text font-display text-2xl font-bold tracking-widest uppercase animate-pulse z-20 pointer-events-none">
            {worldsDict.mapLoading || "Разворачиваем пергамент..."}
          </div>
        )}

        {!loading && missions.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-text font-display text-xl font-bold z-20 pointer-events-none">
            {worldsDict.mapEmpty || "Пираты украли карту. Задания не найдены."}
          </div>
        )}

        {/* Холст пергамента */}
        <div 
          ref={mapScrollRef} 
          style={{ width: `${Math.max(150, missions.length * 13)}vw` }}
          className="relative h-[70vh] ml-6 mr-6 rounded-[2.5rem] border-8 border-[#5c3a21] bg-[#dcb98a] shadow-2xl shrink-0 overflow-hidden"
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

              {/* Названия курсов над первой миссией каждого */}
              {missions.map((mission, index) => {
                if (index > 0 && missions[index - 1].track_id === mission.track_id) return null;
                if (!mission.track_title) return null;
                const coords = getCoords(index, missions.length);
                return (
                  <span
                    key={`course-${mission.id}`}
                    aria-hidden="true"
                    className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[210%] whitespace-nowrap rounded-full border border-[#5c3a21]/50 bg-[#f4e4bc]/90 px-3 py-1 text-xs font-bold uppercase tracking-widest text-[#5c3a21]"
                    style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
                  >
                    {mission.track_title}
                  </span>
                );
              })}

              {/* Узлы миссий */}
              {missions.map((mission, index) => {
                const coords = getCoords(index, missions.length);
                const statusVal = missionStatus(mission);
                const isCompleted = statusVal === "completed";
                const isLocked = statusVal === "locked";
                const isActive = statusVal === "available";
                const isCurrent = mission.id === current?.id;
                const Icon = isCompleted ? CheckCircle : (isLocked ? Lock : XIcon);
                const title = missionTitle(mission, language, worldsDict.missionFallback || "Миссия");
                const statusLabel = isCompleted
                  ? worldsDict.statusCompleted || "Пройдено"
                  : isLocked
                  ? worldsDict.statusLocked || "Закрыто"
                  : worldsDict.statusAvailable || "Доступно";
                const reason = isLocked ? lockReason(mission, missions, t) : "";
                // подпись всегда видна у текущей миссии, у остальных раскрывается по наведению и фокусу
                const labelClass = isCurrent
                  ? "max-w-[220px] opacity-100 ml-3 pr-4"
                  : "max-w-0 opacity-0 group-hover:max-w-[220px] group-hover:opacity-100 group-hover:ml-3 group-hover:pr-4 group-focus-visible:max-w-[220px] group-focus-visible:opacity-100 group-focus-visible:ml-3 group-focus-visible:pr-4";

                return (
                  <Link
                    href={isLocked ? "#" : `/missions/${mission.id}`}
                    key={mission.id}
                    aria-label={`${title}. ${statusLabel}${reason ? `. ${reason}` : ""}`}
                    aria-disabled={isLocked ? "true" : undefined}
                    title={reason || title}
                    onClick={(e) => {
                      if (!isLocked) return;
                      e.preventDefault();
                      // закрытая миссия объясняет, чего не хватает, а не молчит
                      if (reason) toast(reason);
                    }}
                    className={`mission-node absolute transform -translate-x-1/2 -translate-y-1/2 group z-10 rounded-full outline-none focus-visible:ring-4 focus-visible:ring-[#8e1d1d]/60 ${isLocked ? 'cursor-default' : 'cursor-pointer'}`}
                    style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
                  >
                    {isActive && (
                      <span className="absolute inset-0 rounded-full bg-[#8e1d1d]/40 animate-ping motion-reduce:animate-none group-hover:bg-[#8e1d1d]/60 transition-colors duration-300" style={{ zIndex: -1 }}></span>
                    )}

                    <div className={`flex items-center p-1 md:p-1.5 rounded-full border-2 transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] shadow-[0_4px_10px_rgba(62,39,35,0.4)] group-hover:scale-110
                      ${isLocked ? 'bg-[#c4a173] border-[#8b5a2b]' : 'bg-[#f4e4bc] border-[#8e1d1d] group-hover:bg-[#fff0d4] group-hover:shadow-[0_0_25px_rgba(142,29,29,0.5)]'}
                    `}>
                      <div className={`flex-shrink-0 w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full transition-all duration-500 shadow-inner group-hover:shadow-[inset_0_0_15px_rgba(0,0,0,0.4)]
                        ${isLocked ? 'text-[#8b5a2b] bg-transparent' : (isCompleted ? 'bg-[#2e633a] text-[#f4e4bc]' : 'bg-[#8e1d1d] text-[#f4e4bc]')}
                      `}>
                        <Icon size={isLocked ? 18 : 22} strokeWidth={isLocked ? 2 : 2.5} className="transition-transform duration-500 group-hover:scale-125 group-hover:rotate-12" />
                      </div>

                      <div className={`overflow-hidden whitespace-nowrap transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${labelClass}`}>
                        <p className={`text-sm font-display font-bold tracking-wide ${isLocked ? 'text-[#5c3a21]' : 'text-[#3e2723]'}`}>
                          {title}
                        </p>
                        <p className={`text-xs font-bold uppercase tracking-widest mt-0.5 ${isLocked ? 'text-[#8b5a2b]' : 'text-[#8e1d1d]'}`}>
                          {statusLabel}
                        </p>
                      </div>
                    </div>
                  </Link>
                );
              })}

              {/* Маркер героя: стоит у текущего узла и «доезжает» к нему при входе */}
              <div
                className="absolute inset-0 z-20 pointer-events-none"
                style={{
                  transform: `translate(${heroCoords.x}%, ${heroCoords.y}%)`,
                  transition: "transform 0.7s cubic-bezier(0.4,0,0.2,1)",
                }}
                aria-hidden="true"
              >
                <div className="absolute left-0 top-0 -translate-x-1/2 -translate-y-[150%]">
                  <span className="relative grid place-items-center">
                    <span className="absolute -inset-2 rounded-full bg-[#8e1d1d]/30 animate-ping motion-reduce:animate-none" />
                    <span className="grid h-8 w-8 place-items-center rounded-full border-2 border-[#8e1d1d] bg-[#f4e4bc] text-[#8e1d1d] shadow-[0_4px_10px_rgba(62,39,35,0.5)]">
                      <Compass size={17} strokeWidth={2.5} />
                    </span>
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Телефон: горизонтальная карта с пиннингом и подписями по hover не работает на тач-экранах,
          поэтому там вертикальная тропа с прогрессом. */}
      <MissionPath missions={missions} loading={loading} />
    </Layout>
  );
}