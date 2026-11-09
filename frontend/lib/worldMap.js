// Геометрия карты миров (экран /worlds и лендинг). Чистые функции без React и DOM,
// поэтому их проверяют тесты node --test.
//
// Координаты узлов даны в процентах холста: x растёт слева направо, y качается вокруг середины.

const X_VARIATIONS = [0, 4, -3, 5, -4, 2, -2, 3];
const CP1_Y = [60, -55, 65, -50, 70, -60, 55, -65];
const CP2_Y = [-60, 55, -65, 50, -70, 60, -55, 65];
const CP1_X = [0.2, 0.25, 0.2, 0.3, 0.25, 0.2, 0.3, 0.25];
const CP2_X = [0.8, 0.75, 0.8, 0.7, 0.75, 0.8, 0.7, 0.75];

// Общий атлас: карта героя без класса (и лендинг).
export const DEFAULT_WORLD = {
  id: "atlas",
  offsets: [15, -25, 5, -30, 20, -10, 35, -20],
  landmarks: [],
  tint: null,
  hero: "compass",
};

// Мир каждого класса героя. Учебный путь у всех один (те же миссии в том же порядке): класс меняет
// саму карту — форму тропы, ориентиры, цвет пергамента и знак героя. Ключ — id класса (ClassRole):
// 1 Python-спеллблейд, 2 Арканист Django, 3 DevOps-рейнджер.
export const WORLDS = {
  // змеиная тропа джунглей: ровные волны вверх-вниз
  1: {
    id: "serpent",
    offsets: [22, -24, 26, -22, 24, -26, 20, -24],
    landmarks: ["🐍", "🏛️", "🌿", "🗡️", "🌴", "✨"],
    tint: "47, 107, 69",
    hero: "sword",
  },
  // ярусы башни: тропа поднимается ступенями и снова спускается к следующей башне
  2: {
    id: "arcane",
    offsets: [30, 16, 2, -14, -28, -12, 4, 20],
    landmarks: ["🔮", "🏰", "📚", "🌙", "🕯️", "✨"],
    tint: "91, 63, 140",
    hero: "wand",
  },
  // пограничье: привалы парами на одной высоте, между ними перевалы
  3: {
    id: "frontier",
    offsets: [12, 12, -22, -22, 26, 26, -14, -14],
    landmarks: ["🌲", "⛺", "🏔️", "⚙️", "🔥", "🚀"],
    tint: "120, 92, 40",
    hero: "pine",
  },
};

// Мир героя по id его класса; без класса (или с неизвестным) — общий атлас.
export function worldFor(classRoleId) {
  return WORLDS[Number(classRoleId)] || DEFAULT_WORLD;
}

// Где стоит узел index из total (в процентах холста).
export function mapCoords(index, total, world = DEFAULT_WORLD) {
  const offsets = world.offsets;
  const step = total > 1 ? 72 / (total - 1) : 0;
  let xVar = X_VARIATIONS[index % X_VARIATIONS.length];
  if (index === 0 || index === total - 1) xVar = 0;
  return {
    x: 8 + index * step + xVar,
    y: 50 + offsets[index % offsets.length],
  };
}

// Строка d для SVG-тропы через все узлы; для пустой карты пустая строка.
export function mapPath(total, world = DEFAULT_WORLD) {
  if (!total || total < 1) return "";
  const first = mapCoords(0, total, world);
  let path = `M ${first.x} ${first.y}`;
  for (let i = 1; i < total; i++) {
    const prev = mapCoords(i - 1, total, world);
    const curr = mapCoords(i, total, world);
    const cp1X = prev.x + (curr.x - prev.x) * CP1_X[i % CP1_X.length];
    const cp1Y = prev.y + CP1_Y[i % CP1_Y.length];
    const cp2X = prev.x + (curr.x - prev.x) * CP2_X[i % CP2_X.length];
    const cp2Y = curr.y + CP2_Y[i % CP2_Y.length];
    path += ` C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${curr.x} ${curr.y}`;
  }
  return path;
}

// Ориентиры стоят в верхней или нижней полосе холста: узлы миссий занимают середину (y 20–80),
// подписи областей — самый низ.
export const LANDMARK_TOP = 12;
export const LANDMARK_BOTTOM = 86;

// Ориентиры мира: по одному между соседними миссиями, в той полосе (верх или низ), что дальше от обоих
// соседних узлов, чтобы ни один не закрывал миссию. Чисто декоративные.
export function mapLandmarks(total, world = DEFAULT_WORLD) {
  if (!world.landmarks.length || total < 2) return [];
  const marks = [];
  for (let i = 0; i < total - 1; i++) {
    const a = mapCoords(i, total, world);
    const b = mapCoords(i + 1, total, world);
    const roomAbove = Math.min(a.y, b.y) - LANDMARK_TOP;
    const roomBelow = LANDMARK_BOTTOM - Math.max(a.y, b.y);
    marks.push({
      x: (a.x + b.x) / 2,
      y: roomAbove >= roomBelow ? LANDMARK_TOP : LANDMARK_BOTTOM,
      glyph: world.landmarks[i % world.landmarks.length],
    });
  }
  return marks;
}

// Где подписать области мира: равные доли ширины, у самого нижнего края холста.
export function mapRegions(count) {
  if (!count || count < 1) return [];
  return Array.from({ length: count }, (_, i) => ({ x: ((i + 0.5) * 100) / count, y: 95 }));
}
