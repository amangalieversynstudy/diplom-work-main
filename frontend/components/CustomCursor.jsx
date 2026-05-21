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

    gsap.set(cursorEl, { xPercent: -50, yPercent: -50 });
    gsap.set(followerEl, { xPercent: -50, yPercent: -50 });

    const onMouseMove = (e) => {
      gsap.to(cursorEl, { x: e.clientX, y: e.clientY, duration: 0.1, ease: "power2.out" });
      gsap.to(followerEl, { x: e.clientX, y: e.clientY, duration: 0.6, ease: "power3.out" });
    };

    const onMouseEnter = (e) => {
      if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) {
        gsap.to(cursorEl, { scale: 0, opacity: 0, duration: 0.3 });
        gsap.to(followerEl, {
          scale: 1.5,
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          borderColor: "rgba(16, 185, 129, 0.6)",
          duration: 0.3,
        });
      }
    };

    const onMouseLeave = (e) => {
      if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) {
        gsap.to(cursorEl, { scale: 1, opacity: 1, duration: 0.3 });
        gsap.to(followerEl, {
          scale: 1,
          backgroundColor: "transparent",
          borderColor: "rgba(148, 163, 184, 0.4)",
          duration: 0.3,
        });
      }
    };

    // Split-screen fix: при alt-tab / split-screen показываем системный курсор
    const onWindowBlur = () => {
      document.body.classList.add("native-cursor");
      gsap.to([cursorEl, followerEl], { opacity: 0, duration: 0.15 });
    };
    const onWindowFocus = () => {
      document.body.classList.remove("native-cursor");
      gsap.to([cursorEl, followerEl], { opacity: 1, duration: 0.15 });
    };

    window.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseover", onMouseEnter);
    document.addEventListener("mouseout", onMouseLeave);
    window.addEventListener("blur", onWindowBlur);
    window.addEventListener("focus", onWindowFocus);

    if (!document.hasFocus()) {
      document.body.classList.add("native-cursor");
      gsap.set([cursorEl, followerEl], { opacity: 0 });
    }

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseover", onMouseEnter);
      document.removeEventListener("mouseout", onMouseLeave);
      window.removeEventListener("blur", onWindowBlur);
      window.removeEventListener("focus", onWindowFocus);
      document.body.classList.remove("native-cursor");
    };
  }, []);

  return (
    <>
      <div ref={cursorRef} className="fixed top-0 left-0 w-2 h-2 bg-emerald-500 rounded-full pointer-events-none z-[9999] hidden md:block will-change-transform" />
      <div ref={followerRef} className="fixed top-0 left-0 w-10 h-10 border-2 border-slate-400/40 rounded-full pointer-events-none z-[9998] hidden md:block will-change-transform" />
    </>
  );
}
