import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Link from "next/link";
import { ArrowRight, Code, Sparkles } from "lucide-react";

export default function AnimatedHero() {
  const container = useRef(null);

  useGSAP(
    () => {
      const tl = gsap.timeline();

      // Анимация бейджика (выплывает сверху)
      tl.fromTo(
        ".hero-badge",
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.8, ease: "power3.out" }
      );

      // Анимация строк заголовка (появляются по очереди)
      tl.fromTo(
        ".hero-title-line",
        { y: 60, opacity: 0 },
        { y: 0, opacity: 1, duration: 1, stagger: 0.15, ease: "expo.out" },
        "-=0.4"
      );

      // Анимация описания
      tl.fromTo(
        ".hero-desc",
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 1, ease: "power3.out" },
        "-=0.6"
      );

      // Анимация кнопок
      tl.fromTo(
        ".hero-btn",
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.8, stagger: 0.15, ease: "power3.out" },
        "-=0.6"
      );
    },
    { scope: container }
  );

  return (
    <section
      ref={container}
      className="relative min-h-screen flex flex-col justify-center items-center overflow-hidden bg-transparent text-text px-4 transition-colors duration-300"
    >

      <div className="z-10 flex flex-col items-center text-center max-w-4xl mt-16">
        <div className="hero-badge inline-flex items-center gap-2 px-4 py-2 rounded-full bg-surface border border-border shadow-sm mb-8 backdrop-blur-md transition-colors duration-300">
          <Sparkles className="w-4 h-4 text-gold" />
          <span className="text-sm font-medium tracking-wide text-muted">
            Новая эра обучения
          </span>
        </div>

        <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 overflow-hidden">
          <div className="hero-title-line text-text">Изучай код через</div>
          <div className="hero-title-line text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent pb-2">
            эпические приключения
          </div>
        </h1>

        <p className="hero-desc text-lg md:text-xl text-muted mb-10 max-w-2xl transition-colors duration-300">
          Проходи миссии, решай алгоритмические задачи и прокачивай своего
          персонажа. Твой путь от новичка до легендарного разработчика начинается здесь.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto">
          <Link
            href="/register"
            className="hero-btn group relative inline-flex items-center justify-center gap-2 px-8 py-4 bg-primary text-white shadow-glow rounded-2xl font-semibold overflow-hidden transition-all hover:scale-105 hover:shadow-glow-lg active:scale-95 border border-primary-dk"
          >
            <span className="relative z-10">Начать игру</span>
            <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
          </Link>

          <Link
            href="/worlds"
            className="hero-btn inline-flex items-center justify-center gap-2 px-8 py-4 bg-surface border border-border hover:bg-panel text-text shadow-sm rounded-2xl font-semibold transition-all active:scale-95 backdrop-blur-sm"
          >
            <Code className="w-5 h-5" />
            Карта миров
          </Link>
        </div>
      </div>
    </section>
  );
}