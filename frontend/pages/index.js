import { useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import AnimatedHero from "../components/AnimatedHero";
import TransitionLink from "../components/TransitionLink";
import {
  Map, Swords, Compass, Crown, Sparkles,
  ChevronRight, BookOpen, Code2, Zap,
} from "lucide-react";
import { useDictionary } from "../lib/i18n";
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
    <div className="stat-item flex flex-col items-center gap-2 p-4 sm:p-6 rounded-3xl border border-border bg-panel shadow-sm hover:shadow-md transition-shadow text-center">
      <div className="w-12 h-12 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-2 text-primary">
        <Icon size={20} />
      </div>
      <p className="font-display text-3xl sm:text-4xl font-bold text-text leading-none">
        {isNaN(parseInt(value, 10)) ? value : counted}
        {!isNaN(parseInt(value, 10)) && value.includes("+") && "+"}
      </p>
      <p className="text-[11px] sm:text-xs font-semibold uppercase tracking-widest text-muted">{label}</p>
    </div>
  );
}

/* ─── Track program card ─────────────────────────────────────── */
function TrackCard({ track }) {
  const Icon = track.icon;
  return (
    <TransitionLink href="/worlds" className="track-card block text-left cursor-pointer group relative rounded-3xl border border-border bg-panel transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:shadow-slate-200/50 dark:hover:shadow-black/20">
      {/* Top line accent */}
      <div className="absolute top-0 left-0 right-0 h-1 opacity-70"
        style={{ background: `linear-gradient(90deg, transparent, ${track.dot}, transparent)` }} />

      <div className="p-6 md:p-8">
        <div className="flex items-start justify-between mb-6">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-panel border border-border group-hover:scale-110 transition-transform duration-300">
            <Icon size={28} style={{ color: track.dot }} />
          </div>
          <span className="text-[11px] font-bold uppercase tracking-widest px-3 py-1.5 rounded-full bg-panel text-muted border border-border">
            {track.label}
          </span>
        </div>

        <h3 className="font-display text-xl md:text-2xl font-bold text-text mb-3 transition-colors" style={{ '--tw-hover-color': track.dot }}>
          {track.title}
        </h3>
        <p className="text-sm text-muted leading-relaxed mb-8 h-24">{track.desc}</p>

        <div className="flex items-center justify-end text-sm font-medium border-t border-border pt-5">
          <span style={{ color: track.dot }}>{track.xp}</span>
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

  const STATS = [
    { value: "84",  label: homeDict.stats?.totalMissions || "Всего миссий",    icon: Swords  },
    { value: "4",   label: homeDict.stats?.learningWorlds || "Учебных миров",   icon: Map     },
    { value: "3",   label: homeDict.stats?.heroClasses || "Классов героев",      icon: Crown   },
  ];

  const TRACKS = [
    {
      id: 1,
      label: homeDict.tracks?.[0]?.label || "Основы",
      title: homeDict.tracks?.[0]?.title || "Основы Python",
      desc: homeDict.tracks?.[0]?.desc || "Изучите переменные, циклы, функции и структуры данных через практические квесты на Островах Новичков.",
      xp: "1 200 XP",
      missions: 12,
      icon: BookOpen,
      dot: "#10B981",
    },
    {
      id: 2,
      label: homeDict.tracks?.[1]?.label || "Средний уровень",
      title: homeDict.tracks?.[1]?.title || "ООП и Алгоритмы",
      desc: homeDict.tracks?.[1]?.desc || "Откройте для себя объектно-ориентированное проектирование и изучите сортировку, поиск и рекурсию на Рубеже Адептов.",
      xp: "2 400 XP",
      missions: 18,
      icon: Code2,
      dot: "#F59E0B",
    },
    {
      id: 3,
      label: homeDict.tracks?.[2]?.label || "Продвинутый",
      title: homeDict.tracks?.[2]?.title || "Django и REST API",
      desc: homeDict.tracks?.[2]?.desc || "Создавайте реальные веб-приложения, конечные точки REST и развертывайте свой первый бэкенд в Мифическом Просторе.",
      xp: "3 600 XP",
      missions: 24,
      icon: Zap,
      dot: "#3B82F6",
    },
    {
      id: 4,
      label: homeDict.tracks?.[3]?.label || "Элита",
      title: homeDict.tracks?.[3]?.title || "Готовность к Junior",
      desc: homeDict.tracks?.[3]?.desc || "Docker, CI/CD, тестирование и системный дизайн — все, что вам нужно для вашей первой работы с Django.",
      xp: "5 000 XP",
      missions: 30,
      icon: Crown,
      dot: "#8B5CF6",
    },
  ];

  const HOW_IT_WORKS = [
    {
      num: "01",
      title: homeDict.howItWorks?.[0]?.title || "Выберите класс героя",
      body: homeDict.howItWorks?.[0]?.body || "Выберите Воина, Мага или Разбойника — каждый класс формирует ваш путь обучения и открывает уникальные миссии.",
    },
    {
      num: "02",
      title: homeDict.howItWorks?.[1]?.title || "Исследуйте карту мира",
      body: homeDict.howItWorks?.[1]?.body || "Путешествуйте по красиво иллюстрированным учебным мирам. Каждый остров содержит тематические миссии, которые основываются друг на друге.",
    },
    {
      num: "03",
      title: homeDict.howItWorks?.[2]?.title || "Проходите Сюжет → Викторину → Код",
      body: homeDict.howItWorks?.[2]?.body || "Каждая миссия следует одному и тому же трехэтапному циклу: прочитайте историю, ответьте на теоретические вопросы, а затем выполните реальный код.",
    },
    {
      num: "04",
      title: homeDict.howItWorks?.[3]?.title || "Зарабатывайте XP и повышайте уровень",
      body: homeDict.howItWorks?.[3]?.body || "Каждое действие вознаграждается опытом. Поднимайтесь в таблице лидеров и открывайте новый контент, пока растете от Новичка до Элиты.",
    },
  ];

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

    // Добавляем легкую анимацию "парения" для карточек
    gsap.utils.toArray([".stat-item", ".track-card"]).forEach(card => {
      gsap.to(card, {
        y: (Math.random() * -12) - 6, // смещение вверх от -6px до -18px
        duration: Math.random() * 2 + 3, // длительность от 3 до 5 секунд
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: Math.random() * 1.5,
      });
    });
  }, []);

  return (
    <Layout>

      <AnimatedHero />

      {/* ══════════════════════════════════════════
          STATS STRIP
      ══════════════════════════════════════════ */}
      <section className="stats-strip py-14 border-y border-border bg-panel/50 transition-colors duration-300">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6 max-w-6xl mx-auto px-4 sm:px-6">
          {STATS.map((s, i) => (
            <StatCard key={s.label} {...s} delay={i * 120} />
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          LEARNING TRACKS / PROGRAMS
      ══════════════════════════════════════════ */}
      <section className="tracks-section py-20 bg-surface transition-colors duration-300">
        <div className="mb-12 md:mb-16 max-w-6xl mx-auto px-4 sm:px-6">
          <p className="text-xs font-bold uppercase tracking-widest text-primary mb-3">{homeDict.tracks_eyebrow || "Учебные Треки"}</p>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text leading-tight max-w-lg">
              {homeDict.tracks_headline_1 || "Четыре мира."}<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">{homeDict.tracks_headline_2 || "Одна цель."}</span>
            </h2>
            <p className="text-muted text-sm sm:text-base max-w-sm leading-relaxed">
              {homeDict.tracks_desc || "Каждый мир — это структурированный трек, который проведёт тебя от основ до production-ready Django-разработчика."}
            </p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-6 max-w-6xl mx-auto px-4 sm:px-6">
          {TRACKS.map((track) => (
            <TrackCard key={track.id} track={track} />
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          HOW IT WORKS
      ══════════════════════════════════════════ */}
      <section className="hiw-section py-20 border-t border-border bg-panel/50 transition-colors duration-300">
        <div className="grid md:grid-cols-[0.9fr,1.1fr] gap-12 md:gap-16 items-start max-w-6xl mx-auto px-4 sm:px-6">
          {/* Left sticky label */}
          <div className="md:sticky md:top-28">
            <p className="text-xs font-bold uppercase tracking-widest text-accent mb-3">{homeDict.howitworks_eyebrow || "Процесс"}</p>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text leading-tight">
              {homeDict.howitworks_headline_1 || "Как разворачивается"}<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent to-amber-700">{homeDict.howitworks_headline_2 || "приключение."}</span>
            </h2>
            <p className="text-muted text-sm sm:text-base leading-relaxed mt-5 max-w-sm">
              {homeDict.howitworks_desc || "Цикл прост, но само путешествие захватывает дух. Каждая механика создана для того, чтобы ты продолжал писать код."}
            </p>
            <TransitionLink 
              href="/worlds"
              className="mt-8 inline-flex items-center justify-center gap-2 px-5 py-2.5 sm:px-6 sm:py-3 bg-accent text-white shadow-lg shadow-amber-600/25 rounded-2xl font-semibold overflow-hidden transition-all hover:scale-105 active:scale-95"
            >
              <Compass size={18} /> {homeDict.howitworks_cta || "Начать исследование"}
            </TransitionLink>
          </div>

          {/* Right steps */}
          <div className="space-y-5">
            {HOW_IT_WORKS.map((step) => (
              <div
                key={step.num}
                className="hiw-item group flex gap-4 sm:gap-5 p-4 sm:p-6 rounded-3xl border border-border bg-panel shadow-sm hover:shadow-md transition-all duration-300 hover:-translate-y-1"
              >
                <div className="flex-shrink-0 w-12 h-12 sm:w-14 sm:h-14 rounded-2xl border border-sky-100 dark:border-sky-500/20 bg-sky-50 dark:bg-sky-500/10 flex items-center justify-center">
                  <span className="font-mono text-lg font-bold text-sky-600">{step.num}</span>
                </div>
                <div>
                  <h3 className="font-display text-lg sm:text-xl font-bold text-text mb-2 group-hover:text-sky-600 transition-colors">
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
      <section className="cta-section py-20 px-4 sm:px-6 max-w-6xl mx-auto">
        <div className="cta-inner relative rounded-[2.5rem] border border-border bg-panel shadow-xl shadow-slate-200/50 dark:shadow-black/20 overflow-hidden text-center px-6 py-16 sm:px-8 sm:py-20 transition-colors duration-300">
          {/* Decorative orbs inside CTA */}
          <div className="absolute -top-20 -left-20 w-64 h-64 rounded-full bg-primary/10 blur-3xl pointer-events-none animate-float" />
          <div className="absolute -bottom-20 -right-20 w-64 h-64 rounded-full bg-accent/10 blur-3xl pointer-events-none animate-float" style={{ animationDelay: "3s" }} />
          {/* Top shimmer line */}
          <div className="absolute top-0 left-16 right-16 h-px"
            style={{ background: "linear-gradient(90deg, transparent, var(--primary-selection), transparent)" }} />

          <div className="relative z-10 max-w-2xl mx-auto">
            <p className="text-xs font-bold uppercase tracking-widest text-primary mb-4">{homeDict.cta_eyebrow || "Готов начать?"}</p>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text mb-6 leading-tight">
              {homeDict.cta_headline_1 || "Твой путь героя"}<br />
              {homeDict.cta_headline_mid || "начинается "}<span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">{homeDict.cta_headline_2 || "прямо сейчас."}</span>
            </h2>
            <p className="text-muted text-base sm:text-lg leading-relaxed mb-10 max-w-lg mx-auto">
              {homeDict.cta_desc || "Присоединяйся к тысячам учеников, превращающих изучение Python в реальный опыт разработки — миссия за миссией."}
            </p>
            <div className="flex flex-wrap gap-3 justify-center">
              <TransitionLink href="/register"
                className="group relative inline-flex items-center justify-center gap-2 px-6 py-3 md:px-8 md:py-4 bg-primary text-white shadow-glow rounded-2xl font-semibold overflow-hidden transition-all hover:scale-105 hover:shadow-glow-lg active:scale-95 border border-primary-dk"
              >
                <Sparkles size={18} /> {homeDict.cta_button1 || "Создать аккаунт"}
                <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </TransitionLink>
              <TransitionLink href="/worlds"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 md:px-8 md:py-4 bg-surface border border-border hover:bg-panel text-text shadow-sm rounded-2xl font-semibold transition-all active:scale-95"
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
