// Титул героя: звание по уровню (лестница та же, что в game/fixtures/ranks.json)
// и, если есть, эпитет по самому весомому открытому достижению.

export const LEVEL_TITLES = [
  { min: 1, key: "novice" },
  { min: 2, key: "apprentice" },
  { min: 5, key: "mage" },
  { min: 10, key: "archmage" },
  { min: 20, key: "grandWizard" },
];

// От самого весомого к менее весомому; first_mission и level_5 не берём: они дублируют уровень.
export const TITLE_ACHIEVEMENTS = ["track_complete", "ten_missions", "streak_7", "five_missions"];

/**
 * titleFor(level, achievements) → { rank, badge }.
 * rank: ключ звания (novice, apprentice, mage, archmage, grandWizard);
 * badge: слаг достижения-эпитета или null. achievements: массив слагов
 * или элементов {slug, earned}; открытыми считаются слаги и элементы с earned !== false.
 */
export function titleFor(level, achievements) {
  const lvl = Math.max(1, Math.trunc(Number(level)) || 1);
  let rank = LEVEL_TITLES[0].key;
  for (const step of LEVEL_TITLES) {
    if (lvl >= step.min) rank = step.key;
  }
  const earned = new Set(
    (Array.isArray(achievements) ? achievements : [])
      .filter((a) => a && (typeof a === "string" || a.earned !== false))
      .map((a) => (typeof a === "string" ? a : a.slug))
  );
  const badge = TITLE_ACHIEVEMENTS.find((slug) => earned.has(slug)) || null;
  return { rank, badge };
}
