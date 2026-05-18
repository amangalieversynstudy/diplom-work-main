import { useEffect, useRef } from "react";
import gsap from "gsap";

export default function CustomCursor() {
  const cursorRef = useRef(null);
  const followerRef = useRef(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Центрируем курсор относительно его координат
    gsap.set(cursorRef.current, { xPercent: -50, yPercent: -50 });
    gsap.set(followerRef.current, { xPercent: -50, yPercent: -50 });

    const onMouseMove = (e) => {
      // Основная точка двигается мгновенно
      gsap.to(cursorRef.current, { x: e.clientX, y: e.clientY, duration: 0.1, ease: "power2.out" });
      // Кольцо тянется с легкой задержкой
      gsap.to(followerRef.current, { x: e.clientX, y: e.clientY, duration: 0.6, ease: "power3.out" });
    };

    const onMouseEnter = (e) => {
      // Если навели на интерактивный элемент
      if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) {
        gsap.to(cursorRef.current, { scale: 0, opacity: 0, duration: 0.3 });
        gsap.to(followerRef.current, {
          scale: 1.5,
          backgroundColor: "rgba(16, 185, 129, 0.15)", // полупрозрачный emerald
          borderColor: "rgba(16, 185, 129, 0.6)",
          duration: 0.3,
        });
      }
    };

    const onMouseLeave = (e) => {
      if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) {
        gsap.to(cursorRef.current, { scale: 1, opacity: 1, duration: 0.3 });
        gsap.to(followerRef.current, {
          scale: 1,
          backgroundColor: "transparent",
          borderColor: "rgba(148, 163, 184, 0.4)", // возвращаем серый цвет
          duration: 0.3,
        });
      }
    };

    window.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseover", onMouseEnter);
    document.addEventListener("mouseout", onMouseLeave);

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseover", onMouseEnter);
      document.removeEventListener("mouseout", onMouseLeave);
    };
  }, []);

  return (
    <>
      {/* Главная точка */}
      <div ref={cursorRef} className="fixed top-0 left-0 w-2 h-2 bg-emerald-500 rounded-full pointer-events-none z-[9999] hidden md:block" />
      {/* Плавающее кольцо */}
      <div ref={followerRef} className="fixed top-0 left-0 w-10 h-10 border border-slate-400/40 rounded-full pointer-events-none z-[9998] hidden md:block" />
    </>
  );
}