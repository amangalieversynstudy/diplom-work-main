// Подсказки первого визита: 3–4 короткие карточки на карте и в миссии.
// Какие уже показаны, помнит браузер (localStorage); запросов на сервер нет.
// Файл без импортов: его читает тест как текст.

const SEEN_KEY = "tips_seen_v1";
const OFF_KEY = "tips_off_v1";

export const TIP_ORDER = {
  map: ["map1", "map2"],
  mission: ["mission1", "mission2"],
};

// Страница -> группа подсказок (или null: здесь подсказок нет)
export function tipGroup(pathname) {
  if (pathname === "/worlds") return "map";
  if (typeof pathname === "string" && pathname.startsWith("/missions/")) return "mission";
  return null;
}

export function readTipState(storage) {
  try {
    const raw = storage.getItem(SEEN_KEY);
    const seen = raw ? JSON.parse(raw) : [];
    return { seen: Array.isArray(seen) ? seen : [], off: storage.getItem(OFF_KEY) === "1" };
  } catch {
    // без памяти подсказки не показываем: иначе они повторялись бы при каждом заходе
    return { seen: [], off: true };
  }
}

// Следующая ещё не показанная подсказка группы или null
export function nextTip(group, state) {
  if (!group || state.off) return null;
  const list = TIP_ORDER[group] || [];
  return list.find((id) => !state.seen.includes(id)) || null;
}

export function markTipSeen(storage, id) {
  try {
    const { seen } = readTipState(storage);
    if (!seen.includes(id)) storage.setItem(SEEN_KEY, JSON.stringify([...seen, id]));
  } catch {
    /* ничего */
  }
}

export function turnTipsOff(storage) {
  try {
    storage.setItem(OFF_KEY, "1");
  } catch {
    /* ничего */
  }
}
