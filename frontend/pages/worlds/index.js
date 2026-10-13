import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import Layout from "../../components/Layout";
import MissionPath from "../../components/MissionPath";
import QuestJournal from "../../components/QuestJournal";
import { MapBackdrop, MapTrail } from "../../components/WorldMapParts";
import { toast } from "sonner";
import { useDictionary } from "../../lib/i18n";
import { lockReason, missionTitle } from "../../lib/missions";
import { Lock, CheckCircle, X as XIcon, Compass } from "lucide-react";
import gsap from "gsap";
import { prefersReducedMotion } from "../../lib/motion";
import { mapWalk } from "../../lib/stage";
import { mapCoords, mapPath } from "../../lib/worldMap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Missions, Profile, missionStatus } from "../../lib/api";
import {
  isOnboardingPending,
  clearOnboardingPending,
  readProfileFlags,
  shouldRedirectToClass,
} from "../../lib/onboarding";
import logger from "../../lib/logger";
import { useI18n } from "../../lib/i18n";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// На сервере useLayoutEffect не нужен (и предупреждает), в браузере он не даёт маркеру мигнуть в конечной точке.
const useIsoLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

// Где в прошлый раз стоял герой на карте: идти он должен только после новой победы.
const HERO_SEEN_KEY = "rpg-map-hero-node";

function readSeenNode() {
  try {
    const raw = window.localStorage.getItem(HERO_SEEN_KEY);
    return raw === null ? null : Number(raw);
  } catch {
    return null;
  }
}

function saveSeenNode(node) {
  try {
    window.localStorage.setItem(HERO_SEEN_KEY, String(node));
  } catch {
    /* без памяти маркер просто не анимируется */
  }
}

// Длина пути до точки, ближайшей к узлу (сканируем вперёд от fromLen): так находим узел на тропе.
function lengthNear(path, point, fromLen = 0) {
  const total = path.getTotalLength();
  const stepLen = total / 800;
  let best = fromLen;
  let bestDist = Infinity;
  for (let len = fromLen; len <= total + 1e-6; len += stepLen) {
    const p = path.getPointAtLength(len);
    const dist = (p.x - point.x) ** 2 + (p.y - point.y) ** 2;
    if (dist < bestDist) {
      bestDist = dist;
      best = len;
    }
  }
  return best;
}

export default function Worlds() {
  const dict = useDictionary();
  const { t, language } = useI18n();
  const worldsDict = dict.worldsPage || {};
  const router = useRouter();

  // Пролог: сразу после регистрации ведём выбрать класс. Флаг снимаем при любом исходе,
  // так что возврат на карту больше не перенаправляет.
  useEffect(() => {
    if (!isOnboardingPending()) return;
    let cancelled = false;
    Profile.me()
      .then((me) => {
        if (cancelled) return;
        clearOnboardingPending();
        const { isStaff, hasClass } = readProfileFlags(me);
        if (shouldRedirectToClass({ pending: true, isStaff, hasClass })) {
          router.replace("/class?welcome=1");
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [router]);
  
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const pinContainerRef = useRef(null);
  const mapScrollRef = useRef(null);
  const trailRef = useRef(null);
  const heroRef = useRef(null);
  const swayRef = useRef(null);
  // узел, который ученик уже видел; обновляется, когда герой дошёл
  const seenNodeRef = useRef(undefined);

  useEffect(() => {
    setLoading(true);
    setLoadFailed(false);
    Missions.list()
      .then((data) => {
        const items = Array.isArray(data) ? data : data?.results || [];
        setMissions(items);
      })
      .catch((error) => {
        logger.error(error);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
    // refetch при смене языка или по кнопке «Повторить»
  }, [language, reloadKey]);

  // Координаты узлов и тропа считаются в lib/worldMap.js (их же использует лендинг)
  const getCoords = mapCoords;
  const generatePath = (missionsArr) => mapPath(missionsArr ? missionsArr.length : 0);

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
          // прокрутка короче ширины карты: карта едет быстрее, а под ней не остаётся длинной пустоты
          end: () => `+=${Math.round(moveDist * 0.6)}`,
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
  const heroCoords = getCoords(heroTarget, missions.length);

  // Герой идёт к узлу только после новой победы: сравниваем с узлом, который ученик видел в прошлый раз
  // (localStorage; без него маркер просто стоит на месте). Идёт вдоль тропы, если её путь доступен.
  useIsoLayoutEffect(() => {
    if (loading || missions.length === 0) return undefined;
    if (seenNodeRef.current === undefined) seenNodeRef.current = readSeenNode();
    const walk = mapWalk(seenNodeRef.current, heroTarget);
    saveSeenNode(heroTarget);
    const marker = heroRef.current;
    if (!walk || !marker || prefersReducedMotion()) {
      seenNodeRef.current = heroTarget;
      return undefined;
    }

    const count = missions.length;
    const from = getCoords(walk.from, count);
    const to = getCoords(walk.to, count);
    const trail = trailRef.current;
    let along = null;
    try {
      if (trail && typeof trail.getPointAtLength === "function") {
        const startLen = lengthNear(trail, from);
        const endLen = lengthNear(trail, to, startLen);
        if (endLen > startLen) along = { startLen, endLen };
      }
    } catch {
      along = null;
    }
    const place = (p) => {
      const point = along
        ? trail.getPointAtLength(along.startLen + (along.endLen - along.startLen) * p)
        : { x: from.x + (to.x - from.x) * p, y: from.y + (to.y - from.y) * p };
      marker.style.transform = `translate(${point.x}%, ${point.y}%)`;
      if (swayRef.current) {
        // покачивание на ходу: наклон и лёгкий подскок
        const wave = Math.sin(p * Math.PI * 6);
        swayRef.current.style.transform = `translateY(${-Math.abs(wave) * 4}px) rotate(${wave * 7}deg)`;
      }
    };

    place(0);
    const progress = { p: 0 };
    const tween = gsap.to(progress, {
      p: 1,
      duration: 1.1,
      delay: 0.5,
      ease: "power1.inOut",
      onUpdate: () => place(progress.p),
      onComplete: () => {
        seenNodeRef.current = heroTarget;
        marker.style.transform = `translate(${to.x}%, ${to.y}%)`;
        if (swayRef.current) swayRef.current.style.transform = "";
      },
    });
    return () => {
      tween.kill();
      marker.style.transform = `translate(${to.x}%, ${to.y}%)`;
      if (swayRef.current) swayRef.current.style.transform = "";
    };
    // heroTarget и getCoords выводятся из missions
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, missions]);

  return (
    <Layout hideFooter noBottomPadding>
      <div className="max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 pt-24 pb-4">
        {/* ── Заголовок ── */}
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase tracking-widest mb-3">
            <Compass size={16} />
            <span>{worldsDict.atlasTitle || "Атлас"}</span>
          </div>
          <h1 className="font-title text-4xl md:text-5xl text-text mb-4">
            {worldsDict.mapTitle || "Карта миров"}
          </h1>
          <p className="text-muted text-base md:text-lg max-w-2xl leading-relaxed">
            {worldsDict.mapSubtitle ||
              "Каждый архипелаг таит в себе знания и опасности. Следуй по чернильным тропам, чтобы найти сокровища кода."}
          </p>
        </div>

        <QuestJournal missions={missions} current={current} />
      </div>

      {/* ── Контейнер карты ── */}
      <div ref={pinContainerRef} className="hidden lg:flex w-full h-screen overflow-hidden flex-col justify-center bg-bg relative">
        
        {/* ИСПРАВЛЕНО: Оверлеи состояний теперь зафиксированы по центру экрана и не улетают при прокрутке */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-text font-display text-2xl font-bold tracking-widest uppercase animate-pulse z-20 pointer-events-none">
            {worldsDict.mapLoading || "Разворачиваем пергамент..."}
          </div>
        )}

        {!loading && loadFailed && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-text font-display text-xl font-bold z-20 text-center px-6">
            <span>{worldsDict.mapLoadFailed || "Не удалось загрузить карту. Проверь соединение и попробуй ещё раз."}</span>
            <button
              type="button"
              onClick={() => setReloadKey((k) => k + 1)}
              className="rounded-lg border border-ink/70 bg-ink px-4 py-2 text-sm font-semibold text-straw hover:bg-wood"
            >
              {worldsDict.mapRetry || "Повторить"}
            </button>
          </div>
        )}

        {!loading && !loadFailed && missions.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-text font-display text-xl font-bold z-20 pointer-events-none">
            {worldsDict.mapEmpty || "Пираты украли карту. Задания не найдены."}
          </div>
        )}

        {/* Холст пергамента */}
        <div 
          ref={mapScrollRef} 
          style={{ width: `${Math.max(150, missions.length * 13)}vw` }}
          className="relative h-[70vh] ml-6 mr-6 rounded-[2.5rem] border-8 border-ink bg-parchment shadow-2xl shrink-0 overflow-hidden"
        >
          <MapBackdrop />

          {!loading && missions.length > 0 && (
            <>
              {/* SVG Путь */}
              <MapTrail ref={trailRef} d={generatePath(missions)} />

              {/* Названия курсов над первой миссией каждого */}
              {missions.map((mission, index) => {
                if (index > 0 && missions[index - 1].track_id === mission.track_id) return null;
                if (!mission.track_title) return null;
                const coords = getCoords(index, missions.length);
                return (
                  <span
                    key={`course-${mission.id}`}
                    aria-hidden="true"
                    className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[420%] whitespace-nowrap rounded-full border border-ink/50 bg-parchment-light/90 px-3 py-1 text-xs font-bold uppercase tracking-widest text-ink"
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
                  ? "max-w-[320px] opacity-100 ml-3 pr-4"
                  : "max-w-0 opacity-0 group-hover:max-w-[320px] group-hover:opacity-100 group-hover:ml-3 group-hover:pr-4 group-focus-visible:max-w-[320px] group-focus-visible:opacity-100 group-focus-visible:ml-3 group-focus-visible:pr-4";

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
                    className={`mission-node absolute transform -translate-x-1/2 -translate-y-1/2 group z-10 rounded-full outline-none focus-visible:ring-4 focus-visible:ring-wax/60 ${isLocked ? 'cursor-default' : 'cursor-pointer'}`}
                    style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
                  >
                    {isActive && (
                      <span className="absolute inset-0 rounded-full bg-wax/40 animate-ping motion-reduce:animate-none group-hover:bg-wax/60 transition-colors duration-300" style={{ zIndex: -1 }}></span>
                    )}

                    <div className={`flex items-center p-1 md:p-1.5 rounded-full border-2 transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] shadow-[0_4px_10px_rgba(62,39,35,0.4)] group-hover:scale-110
                      ${isLocked ? 'bg-parchment-lock border-bronze' : 'bg-parchment-light border-wax group-hover:bg-parchment-glow group-hover:shadow-[0_0_25px_rgba(142,29,29,0.5)]'}
                    `}>
                      <div className={`flex-shrink-0 w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full transition-all duration-500 shadow-inner group-hover:shadow-[inset_0_0_15px_rgba(0,0,0,0.4)]
                        ${isLocked ? 'text-bronze bg-transparent' : (isCompleted ? 'bg-[#2e633a] text-parchment-light' : 'bg-wax text-parchment-light')}
                      `}>
                        <Icon size={isLocked ? 18 : 22} strokeWidth={isLocked ? 2 : 2.5} className="transition-transform duration-500 group-hover:scale-125 group-hover:rotate-12" />
                      </div>

                      <div className={`overflow-hidden whitespace-nowrap transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${labelClass}`}>
                        <p className={`truncate text-sm font-display font-bold tracking-wide ${isLocked ? 'text-ink' : 'text-ink-deep'}`}>
                          {title}
                        </p>
                        <p className={`text-xs font-bold uppercase tracking-widest mt-0.5 ${isLocked ? 'text-bronze' : 'text-wax'}`}>
                          {statusLabel}
                        </p>
                        {isLocked && reason ? (
                          <p className="mt-0.5 truncate text-xs italic text-ink">{reason}</p>
                        ) : null}
                      </div>
                    </div>
                  </Link>
                );
              })}

              {/* Маркер героя: стоит у текущего узла; после новой победы идёт к нему от прежнего вдоль тропы */}
              <div
                ref={heroRef}
                className="absolute inset-0 z-[15] pointer-events-none"
                style={{ transform: `translate(${heroCoords.x}%, ${heroCoords.y}%)` }}
                aria-hidden="true"
              >
                <div className="absolute left-0 top-0 -translate-x-1/2 -translate-y-[250%]">
                  <span ref={swayRef} className="relative grid place-items-center">
                    <span className="absolute -inset-2 rounded-full bg-wax/30 animate-ping motion-reduce:animate-none" />
                    <span className="grid h-8 w-8 place-items-center rounded-full border-2 border-wax bg-parchment-light text-wax shadow-[0_4px_10px_rgba(62,39,35,0.5)]">
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