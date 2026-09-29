import { useEffect, useState } from "react";
import { prefersReducedMotion } from "../lib/motion";

/** Число, которое доезжает от нуля до значения (без движения показывает сразу). */
export default function CountUp({ to, duration = 700 }) {
  const target = Number(to);
  const animate = Number.isFinite(target) && !prefersReducedMotion();
  const [value, setValue] = useState(animate ? 0 : target);

  useEffect(() => {
    if (!animate) {
      setValue(target);
      return undefined;
    }
    let frame;
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    // запасной вариант: если кадры не идут (вкладка в фоне), всё равно показать итог
    const done = setTimeout(() => setValue(target), duration + 250);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(done);
    };
  }, [target, animate, duration]);

  return <span className="tabular-nums">{Number.isFinite(target) ? value : to}</span>;
}
