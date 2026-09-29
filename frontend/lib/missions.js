import { missionStatus } from "./api";

/** Название миссии на языке интерфейса. */
export function missionTitle(mission, language, fallback = "") {
  return (
    (language === "en"
      ? mission.title_en || mission.title_ru
      : mission.title_ru || mission.title_en) ||
    mission.title ||
    mission.name ||
    fallback
  );
}

/** Всё, что можно заработать в миссии: XP шагов и бонус за завершение. */
export function missionXp(mission) {
  return (mission.xp_reward || 0) + (mission.tasks || []).reduce((sum, task) => sum + (task.xp_reward || 0), 0);
}

/**
 * Что мешает открыть закрытую миссию: незавершённая предыдущая или недостающий уровень.
 * Пустая строка, если причину назвать нечем.
 */
export function lockReason(mission, missions, t) {
  const byId = Object.fromEntries(missions.map((m) => [m.id, m]));
  const open = (mission.prerequisites || []).find((pre) => missionStatus(byId[pre.id] || {}) !== "completed");
  if (open) return t("worldsPage.mobile.lockedAfter").replace("{title}", open.title);
  if (mission.min_level > 1) return t("worldsPage.mobile.lockedLevel").replace("{n}", mission.min_level);
  return "";
}
