import { useEffect, useRef } from "react";
import gsap from "gsap";

export default function CustomCursor() {
  const cursorRef = useRef(null);
  const followerRef = useRef(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const cursorEl = cursorRef.current;
    const followerEl = followerRef.current;
    if (!cursorEl || !followerEl) return;

    // Установка начальной позиции
    gsap.set([cursorEl, followerEl], { xPercent: -50, yPercent: -50 });

    // Использование quickTo для мгновенного и плавного отклика
    const xTo = gsap.quickTo(cursorEl, "x", { duration: 0.05, ease: "power2.out" });
    const yTo = gsap.quickTo(cursorEl, "y", { duration: 0.05, ease: "power2.out" });
    const xFollow = gsap.quickTo(followerEl, "x", { duration: 0.15, ease: "power2.out" });
    const yFollow = gsap.quickTo(followerEl, "y", { duration: 0.15, ease: "power2.out" });

    const onMouseMove = (e) => {
      xTo(e.clientX);
      yTo(e.clientY);
      xFollow(e.clientX);
      yFollow(e.clientY);
    };

    const onMouseOver = (e) => {
      if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) {
        gsap.to(cursorEl, { scale: 0, opacity: 0, duration: 0.2 });
        gsap.to(followerEl, { scale: 1.5, borderColor: "rgba(16, 185, 129, 0.6)", duration: 0.2 });
      }
    };

    const onMouseOut = (e) => {
      if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) {
        gsap.to(cursorEl, { scale: 1, opacity: 1, duration: 0.2 });
        gsap.to(followerEl, { scale: 1, borderColor: "rgba(148, 163, 184, 0.4)", duration: 0.2 });
      }
    };

    window.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseover", onMouseOver);
    document.addEventListener("mouseout", onMouseOut);

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseover", onMouseOver);
      document.removeEventListener("mouseout", onMouseOut);
    };
  }, []);

  return (
    <>
      <div 
        ref={cursorRef} 
        className="fixed top-0 left-0 w-2 h-2 bg-emerald-500 rounded-full pointer-events-none z-[9999] will-change-transform" 
      />
      <div 
        ref={followerRef} 
        className="fixed top-0 left-0 w-10 h-10 border-2 border-slate-400/40 rounded-full pointer-events-none z-[9998] will-change-transform" 
      />
    </>
  );
}