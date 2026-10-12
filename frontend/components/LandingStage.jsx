import { useEffect, useState } from "react";
import CodemancerStage from "./CodemancerStage";
import { HERO_X_MAX, HERO_X_MIN } from "../lib/stage";
import { prefersReducedMotion } from "../lib/motion";

/**
 * Сцена героя и голема на лендинге. Показывает один раз короткую демонстрацию:
 * герой идёт к врагу, бьёт, голем вздрагивает; дальше сцена засыпает (cm-calm внутри CodemancerStage).
 * Без движения (prefers-reduced-motion) остаётся статичная картинка. Данных с сервера не берёт.
 */
export default function LandingStage() {
  const [heroX, setHeroX] = useState(HERO_X_MIN);
  const [phase, setPhase] = useState("idle");
  const [tick, setTick] = useState(0);
  const [enemyHp, setEnemyHp] = useState(100);

  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const timers = [];
    const at = (ms, fn) => timers.push(setTimeout(fn, ms));
    at(600, () => setHeroX(HERO_X_MAX)); // идёт к врагу
    at(1500, () => {
      // удар: снаряд летит, голем вздрагивает
      setPhase("victory");
      setTick(1);
      setEnemyHp(70);
    });
    at(2900, () => setPhase("idle")); // покой
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="overflow-hidden rounded-2xl border-2 border-[var(--gold-frame)] shadow-xl">
      <CodemancerStage level={1} hpPct={100} mpPct={100} heroX={heroX} enemyHpPct={enemyHp} phase={phase} tick={tick} />
    </div>
  );
}
