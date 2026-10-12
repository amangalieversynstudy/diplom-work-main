import { useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import AnimatedHero from "../components/AnimatedHero";
import LandingStage from "../components/LandingStage";
import LandingMap from "../components/LandingMap";
import TransitionLink from "../components/TransitionLink";
import {
  Map, Swords, Compass, Crown, Sparkles,
  ChevronRight, BookOpen, Code2, Zap,
} from "lucide-react";
import { useDictionary, useI18n } from "../lib/i18n";
import { Tracks } from "../lib/api";
import { unit } from "../lib/plural";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/dist/ScrollTrigger";
import { useGSAP } from "@gsap/react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

/* ─── Tiny helper to animate counters ───────────────────────── */
function useCountUp(target, duration = 1400, delay = 0) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    if (isNaN(parseInt(target, 10))) { setCount(target); return; }
    const num = parseInt(target, 10);
    const start = performance.now() + delay;
    const tick = (now) => {
      const elapsed = Math.max(0, now - start);
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(ease * num));
      if (progress < 1) ref.current = requestAnimationFrame(tick);
    };
    ref.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(ref.current);
  }, [target, duration, delay]);
  return count;
}

/* ─── Stat counter card (with in-view trigger) ───────────────── */
function StatCard({ value, label, icon: Icon, delay }) {
  const counted = useCountUp(value, 1200, delay);
  return (
    <div className="stat-item scroll-frame flex flex-col items-center gap-2 p-4 sm:p-6 text-center">
      <div className="w-12 h-12 rounded-full bg-panel border-2 border-[var(--gold-frame)] flex items-center justify-center mb-2 text-primary">
        <Icon size={20} />
      </div>
      <p className="font-title text-3xl sm:text-4xl text-text leading-none">
        {isNaN(parseInt(value, 10)) ? value : counted}
        {!isNaN(parseInt(value, 10)) && value.includes("+") && "+"}
      </p>
      <p className="text-xs font-semibold uppercase tracking-widest text-muted">{label}</p>
    </div>
  );
}

/* ─── Track program card ─────────────────────────────────────── */
function TrackCard({ track, soonLabel }) {
  const Icon = track.icon;
  // Трек, которого ещё нет, не ссылка: раньше все четыре карточки вели на одну страницу.
  const Root = track.soon ? "div" : TransitionLink;
  const rootProps = track.soon ? { "aria-disabled": "true" } : { href: "/worlds" };
  return (
    <Root
      {...rootProps}
      className={`track-card block text-left group relative rounded-3xl border border-border bg-panel transition-all duration-300 ${
        track.soon
          ? "border-dashed"
          : "cursor-pointer hover:-translate-y-2 hover:shadow-xl hover:shadow-slate-200/50 dark:hover:shadow-black/20"
      }`}
    >
      {/* Top line accent */}
      <div className="absolute top-0 left-0 right-0 h-1 opacity-70"
        style={{ background: `linear-gradient(90deg, transparent, ${track.dot}, transparent)` }} />

      <div className="p-6 md:p-8">
        <div className="flex items-start justify-between mb-6">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-panel border border-border group-hover:scale-110 transition-transform duration-300">
            <Icon size={28} style={{ color: track.dot }} />
          </div>
          <span className="text-xs font-bold uppercase tracking-widest px-3 py-1.5 rounded-full bg-panel text-muted border border-border">
            {track.label}
          </span>
        </div>

        <h3 className="font-display text-xl md:text-2xl font-bold text-text mb-3 transition-colors" style={{ '--tw-hover-color': track.dot }}>
          {track.title}
        </h3>
        <p className="text-sm text-muted leading-relaxed mb-8 h-24">{track.desc}</p>

        <div className="flex items-center justify-end text-sm font-medium border-t border-border pt-5">
          <span style={{ color: track.soon ? undefined : `color-mix(in srgb, ${track.dot} 55%, var(--text))` }} className={track.soon ? "text-muted" : undefined}>
            {track.soon ? soonLabel : track.xp}
          </span>
        </div>
      </div>

      {/* Pixelated glow effect on hover */}
      <div
        className="absolute -inset-px rounded-[inherit] -z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{
          boxShadow: `0 0 0 1px ${track.dot}20, 0 0 0 3px ${track.dot}10, 0 0 0 5px ${track.dot}05`,
          background: `${track.dot}03`,
        }}
      />
    </Root>
  );
}

/* ─── Main Page ──────────────────────────────────────────────── */
export default function Home() {

  const dict = useDictionary();
  const homeDict = dict.home || {};

  const { t, language } = useI18n();

  // Курсы и цифры берём из настоящего каталога: лендинг не должен обещать того, чего нет.
  // Пока каталог грузится (или сервер недоступен), показываем текущие значения.
  const [catalog, setCatalog] = useState(null);
  useEffect(() => {
    let active = true;
    Tracks.list()
      .then((list) => {
        if (active) setCatalog(list);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [language]);

  const COURSE_LOOK = [
    { icon: BookOpen, dot: "#10B981", label: homeDict.basicsLabel || "Основы" },
    { icon: Code2, dot: "#F59E0B", label: homeDict.continuedLabel || "Продолжение" },
  ];
  const courses = (catalog || []).map((track, index) => {
    const missions = (track.worlds || []).flatMap((world) => world.missions || []);
    const xp = missions.reduce(
      (sum, mission) =>
        sum +
        (mission.xp_reward || 0) +
        (mission.tasks || []).reduce((acc, task) => acc + (task.xp_reward || 0), 0),
      0
    );
    const look = COURSE_LOOK[index % COURSE_LOOK.length];
    return {
      id: `course-${track.id}`,
      label: look.label,
      title: track.title,
      desc: track.description,
      xp: `${xp} XP · ${missions.length} ${unit(t, language, "mission", missions.length)}`,
      icon: look.icon,
      dot: look.dot,
      missions: missions.length,
      worlds: (track.worlds || []).length,
    };
  });
  // Свитки на карте лендинга: миссии из того же каталога, без отдельных запросов
  const landingMissions = (catalog || []).flatMap((track) =>
    (track.worlds || []).flatMap((world) => world.missions || [])
  );
  const totalMissions = catalog ? courses.reduce((sum, c) => sum + c.missions, 0) : 16;
  const totalCourses = catalog ? courses.length : 2;

  const STATS = [
    { value: String(totalMissions), label: homeDict.stats?.totalMissions || "Всего миссий", icon: Swords },
    { value: String(totalCourses), label: homeDict.stats?.learningWorlds || "Курсов", icon: Map },
    { value: "3", label: homeDict.stats?.heroClasses || "Классов героев", icon: Crown },
  ];

  const SOON_LOOK = [
    { icon: Zap, dot: "#3B82F6" },
    { icon: Crown, dot: "#8B5CF6" },
  ];
  const soon = (homeDict.soonTracks || []).map((track, index) => ({
    id: `soon-${index}`,
    label: track.label,
    title: track.title,
    desc: track.desc,
    soon: true,
    ...SOON_LOOK[index % SOON_LOOK.length],
  }));
  const TRACKS = [...courses, ...soon];

  const HOW_IT_WORKS = (homeDict.howItWorks || []).map((step, index) => ({
    num: String(index + 1).padStart(2, "0"),
    title: step.title,
    body: step.body,
  }));

  useGSAP(() => {
    // Явный fromTo полностью решает проблему "невидимости"
    gsap.fromTo(".stat-item",
      { y: 40, opacity: 0 },
      { scrollTrigger: { trigger: ".stats-strip", start: "top 85%" }, y: 0, opacity: 1, duration: 0.6, stagger: 0.12, ease: "power2.out" }
    );

    gsap.fromTo(".track-card",
      { y: 60, opacity: 0 },
      { scrollTrigger: { trigger: ".tracks-section", start: "top 80%" }, y: 0, opacity: 1, duration: 0.7, stagger: 0.15, ease: "power3.out" }
    );

    gsap.fromTo(".hiw-item",
      { x: -50, opacity: 0 },
      { scrollTrigger: { trigger: ".hiw-section", start: "top 80%" }, x: 0, opacity: 1, duration: 0.7, stagger: 0.18, ease: "power2.out" }
    );

    gsap.fromTo(".cta-inner",
      { y: 50, opacity: 0 },
      { scrollTrigger: { trigger: ".cta-section", start: "top 85%" }, y: 0, opacity: 1, duration: 0.8, ease: "power3.out" }
    );
  }, []);

  return (
    <Layout>

      <AnimatedHero />

      {/* Первый экран: герой с големом и карта первых свитков */}
      <div className="max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
        <LandingStage />
        <LandingMap missions={landingMissions} />
      </div>

      {/* ══════════════════════════════════════════
          STATS STRIP
      ══════════════════════════════════════════ */}
      <section className="stats-strip py-14 border-y border-border bg-panel/50 transition-colors duration-300">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6 max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
          {STATS.map((s, i) => (
            <StatCard key={s.label} {...s} delay={i * 120} />
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          LEARNING TRACKS / PROGRAMS
      ══════════════════════════════════════════ */}
      <section className="tracks-section py-20 bg-surface transition-colors duration-300">
        <div className="mb-12 md:mb-16 max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
          <p className="text-xs font-bold uppercase tracking-widest text-primary mb-3">{homeDict.tracks_eyebrow || "Учебные Треки"}</p>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text leading-tight max-w-lg">
              {homeDict.tracks_headline_1 || "Один мир."}{" "}<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">{homeDict.tracks_headline_2 || "С него всё начинается."}</span>
            </h2>
            <p className="text-muted text-sm sm:text-base max-w-sm leading-relaxed">
              {homeDict.tracks_desc || "Сейчас открыт вводный курс по Python. Следующие треки готовятся и появятся позже."}
            </p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-6 max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
          {TRACKS.map((track) => (
            <TrackCard key={track.id} track={track} soonLabel={homeDict.soon || "Скоро"} />
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          HOW IT WORKS
      ══════════════════════════════════════════ */}
      <section className="hiw-section py-20 border-t border-border bg-panel/50 transition-colors duration-300">
        <div className="grid md:grid-cols-[0.9fr,1.1fr] gap-12 md:gap-16 items-start max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
          {/* Left sticky label */}
          <div className="md:sticky md:top-28">
            <p className="text-xs font-bold uppercase tracking-widest text-accent mb-3">{homeDict.howitworks_eyebrow || "Процесс"}</p>
            <h2 className="font-title text-3xl sm:text-4xl lg:text-5xl text-text leading-tight">
              {homeDict.howitworks_headline_1 || "Как разворачивается"}{" "}<br />
              <span className="text-accent">{homeDict.howitworks_headline_2 || "приключение."}</span>
            </h2>
            <p className="text-muted text-sm sm:text-base leading-relaxed mt-5 max-w-sm">
              {homeDict.howitworks_desc || "Цикл прост, но само путешествие захватывает дух. Каждая механика создана для того, чтобы ты продолжал писать код."}
            </p>
            <TransitionLink 
              href="/worlds"
              className="scroll-btn mt-8 inline-flex items-center justify-center gap-2 px-5 py-2.5 sm:px-6 sm:py-3 font-medium tracking-wide transition-transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <Compass size={18} /> {homeDict.howitworks_cta || "Начать исследование"}
            </TransitionLink>
          </div>

          {/* Right steps */}
          <div className="space-y-5">
            {HOW_IT_WORKS.map((step) => (
              <div
                key={step.num}
                className="hiw-item scroll-frame group flex gap-4 sm:gap-5 p-4 sm:p-6"
              >
                <div className="flex-shrink-0 w-12 h-12 sm:w-14 sm:h-14 rounded-full border-2 border-[var(--gold-frame)] bg-[var(--wax)] flex items-center justify-center">
                  <span className="font-title text-xl text-[var(--parchment-light)]">{step.num}</span>
                </div>
                <div>
                  <h3 className="font-title text-xl sm:text-2xl text-text mb-2">
                    {step.title}
                  </h3>
                  <p className="text-muted text-sm leading-relaxed">{step.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          CTA SECTION
      ══════════════════════════════════════════ */}
      <section className="cta-section py-20 px-4 sm:px-6 max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto">
        <div className="cta-inner scroll-frame relative overflow-hidden text-center px-6 py-14 sm:px-8 sm:py-16">
          <div className="relative z-10 max-w-2xl mx-auto">
            <p className="text-xs font-bold uppercase tracking-widest text-primary mb-4">{homeDict.cta_eyebrow || "Готов начать?"}</p>
            <h2 className="font-title text-3xl sm:text-4xl lg:text-5xl text-text mb-6 leading-tight">
              {homeDict.cta_headline_1 || "Твой путь героя"}{" "}<br />
              {homeDict.cta_headline_mid || "начинается "}<span className="text-[var(--wax)]">{homeDict.cta_headline_2 || "прямо сейчас."}</span>
            </h2>
            <p className="text-muted text-base sm:text-lg leading-relaxed mb-10 max-w-lg mx-auto">
              {homeDict.cta_desc || "Начни с вводного курса и пройди Python шаг за шагом: история, квиз, код."}
            </p>
            <div className="flex flex-wrap gap-3 justify-center">
              <TransitionLink href="/register"
                className="scroll-btn group inline-flex items-center justify-center gap-2 px-6 py-3 md:px-8 md:py-4 font-medium tracking-wide transition-transform hover:-translate-y-0.5 active:translate-y-0"
              >
                <Sparkles size={18} /> {homeDict.cta_button1 || "Создать аккаунт"}
                <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </TransitionLink>
              <TransitionLink href="/worlds"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 md:px-8 md:py-4 rounded-[10px] border-2 border-[var(--ink)] bg-[var(--parchment)] text-[var(--ink-deep)] font-medium tracking-wide transition-transform hover:-translate-y-0.5 active:translate-y-0"
              >
                <Map size={18} /> {homeDict.cta_button2 || "Карта миров"}
              </TransitionLink>
            </div>
          </div>
        </div>
      </section>

    </Layout>
  );
}
