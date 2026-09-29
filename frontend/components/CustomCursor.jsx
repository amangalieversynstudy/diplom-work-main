import { useEffect, useRef } from "react";
import gsap from "gsap";

// Декоративный кружок, отстающий от системного курсора. Сам системный курсор
// не скрывается (иначе пропадает I-образный курсор в редакторе и системный
// размер курсора). При наведении на интерактивные элементы кружок зеленеет.
export default function CustomCursor() {
  const ringRef = useRef(null);
  const stateRef = useRef("default"); // "default" | "hover"

  useEffect(() => {
    if (typeof window === "undefined") return;

    const ring = ringRef.current;
    if (!ring) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    // Стартовая позиция — центр экрана, чтобы не мерцало в углу
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    gsap.set(ring, { x: cx, y: cy, xPercent: -50, yPercent: -50 });

    const INTERACTIVE = "a, button, input, textarea, select, label, [role='button']";

    const onMouseMove = (e) => {
      const mx = e.clientX;
      const my = e.clientY;

      // Кружок отстаёт
      gsap.to(ring, { x: mx, y: my, duration: 0.55, ease: "power3.out" });

      // Проверяем, над чем курсор — один раз за mousemove
      const el = document.elementFromPoint(mx, my);
      const isInteractive = el && el.closest(INTERACTIVE);

      if (isInteractive && stateRef.current !== "hover") {
        stateRef.current = "hover";
        gsap.to(ring, {
          scale: 1.6,
          borderColor: "rgba(16, 185, 129, 0.8)",
          backgroundColor: "rgba(16, 185, 129, 0.12)",
          duration: 0.25,
        });
      } else if (!isInteractive && stateRef.current !== "default") {
        stateRef.current = "default";
        gsap.to(ring, {
          scale: 1,
          borderColor: "rgba(148, 163, 184, 0.45)",
          backgroundColor: "transparent",
          duration: 0.25,
        });
      }
    };

    // Скрываем кастомный курсор когда окно теряет фокус
    const onBlur = () => gsap.to(ring, { opacity: 0, duration: 0.15 });
    const onFocus = () => gsap.to(ring, { opacity: 1, duration: 0.15 });

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  return (
    <>
      {/* Отстающий кружок */}
      <div
        ref={ringRef}
        aria-hidden="true"
        className="fixed top-0 left-0 w-10 h-10 border-2 rounded-full pointer-events-none z-[9998] hidden md:block will-change-transform"
        style={{ borderColor: "rgba(148,163,184,0.45)", backgroundColor: "transparent" }}
      />
    </>
  );
}
