import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import AnimatedHero from "../components/AnimatedHero";
import LandingStage from "../components/LandingStage";
import LandingMap from "../components/LandingMap";
import TransitionLink from "../components/TransitionLink";
import { Compass, BookOpen, Code2 } from "lucide-react";
import { useDictionary, useI18n } from "../lib/i18n";
import { Tracks } from "../lib/api";
import { unit } from "../lib/plural";
// без анимаций появления по прокрутке: шаги и курсы видны сразу, ничего не «выезжает» при чтении

/* ─── Track program card ─────────────────────────────────────── */
// Только настоящие курсы из каталога: пустые карточки «Скоро» выглядели как недоделка.
function TrackCard({ track }) {
  const Icon = track.icon;
  return (
    <TransitionLink
      href="/worlds"
      className="track-card block text-left group relative rounded-3xl border border-border bg-panel transition-all duration-300 cursor-pointer hover:-translate-y-1 hover:shadow-xl hover:shadow-slate-200/50 dark:hover:shadow-black/20"
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
        <p className="text-sm md:text-base text-muted leading-relaxed mb-8 min-h-[4.5rem]">{track.desc}</p>

        <div className="flex items-center justify-end text-sm font-medium border-t border-border pt-5">
          <span style={{ color: `color-mix(in srgb, ${track.dot} 55%, var(--text))` }}>{track.xp}</span>
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
    </TransitionLink>
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
  const HOW_IT_WORKS = (homeDict.howItWorks || []).map((step, index) => ({
    num: String(index + 1).padStart(2, "0"),
    title: step.title,
    body: step.body,
  }));

  return (
    <Layout>

      <AnimatedHero />

      {/* Первый экран: герой с големом и карта первых свитков */}
      <div className="max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
        <LandingStage />
        <LandingMap missions={landingMissions} />
      </div>

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

        <div className="grid md:grid-cols-2 gap-6 max-w-6xl 2xl:max-w-[80rem] 3xl:max-w-[92rem] 4xl:max-w-[110rem] mx-auto px-4 sm:px-6">
          {courses.map((track) => (
            <TrackCard key={track.id} track={track} />
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
                  <span className="font-title text-xl text-[#f8ecd0]">{step.num}</span>
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

    </Layout>
  );
}
