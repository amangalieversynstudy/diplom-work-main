// Чистые функции игровой сцены (CodemancerStage и карта миров). Без React и без DOM,
// поэтому их можно проверять тестами node --test.
//
// Сцена только показывает то, что страница уже знает (шаги, прогресс, попытки):
// проверка ответов, запросы и цифровой след от неё не зависят.

// Положение героя по X в координатах сцены (viewBox 1408x470). Враг стоит в 470,
// меч героя выступает вперёд на ~46, поэтому последний шаг оставляет зазор перед врагом.
export const HERO_X_MIN = 60;
export const HERO_X_MAX = 360;

// Здоровье героя не падает ниже половины: сцена даёт азарт, а не наказание.
export const HERO_HP_FLOOR = 50;
export const HERO_HP_HIT = 10;

// Энергия попыток: -20 % за проверку, не ниже 20 %.
export const MP_FLOOR = 20;
export const MP_COST = 20;

const num = (value, fallback) => (Number.isFinite(Number(value)) ? Number(value) : fallback);

// Где стоит герой на шаге index из total: шаг 1 у левого края, последний перед врагом.
export function heroXForStep(index, total) {
  const steps = Math.floor(num(total, 0));
  if (steps <= 1) return HERO_X_MIN;
  const i = Math.min(steps - 1, Math.max(0, Math.floor(num(index, 0))));
  return HERO_X_MIN + ((HERO_X_MAX - HERO_X_MIN) * i) / (steps - 1);
}

// Здоровье врага (0..100) = 100 минус доля решённых шагов. Без шагов враг не тронут.
export function enemyHpFromProgress(solved, total) {
  const all = Math.floor(num(total, 0));
  if (all <= 0) return 100;
  const done = Math.min(all, Math.max(0, num(solved, 0)));
  return 100 - (done / all) * 100;
}

// Сколько шагов миссии решено: progress — словарь {id шага: {status}}.
export function solvedCount(tasks, progress) {
  if (!Array.isArray(tasks) || !progress) return 0;
  return tasks.filter((task) => progress[task?.id]?.status === "completed").length;
}

// Здоровье героя после события: failure ранит, success и step лечат до полного.
export function heroHpAfter(prevHp, event) {
  const prev = Math.min(100, Math.max(0, num(prevHp, 100)));
  if (event === "failure") return Math.min(prev, Math.max(HERO_HP_FLOOR, prev - HERO_HP_HIT));
  if (event === "success" || event === "step") return 100;
  return prev;
}

// Энергия попыток после события: attempt тратит, step наполняет. Только картинка, ничего не блокирует.
export function mpAfter(prevMp, event) {
  const prev = Math.min(100, Math.max(0, num(prevMp, 100)));
  if (event === "attempt") return Math.min(prev, Math.max(MP_FLOOR, prev - MP_COST));
  if (event === "step") return 100;
  return prev;
}

// Оттенки голема (hue-rotate, градусы): у каждой миссии свой противник без новых спрайтов.
export const ENEMY_HUES = [0, 150, 205, 265, 325, 95];

export function enemyHueForMission(key) {
  const n = Math.floor(num(key, 0));
  const size = ENEMY_HUES.length;
  return ENEMY_HUES[((n % size) + size) % size];
}

// Карта: если текущий узел вырос по сравнению с прошлым показом, герой идёт {from, to};
// иначе (первый показ, тот же узел, откат) возвращаем null, и маркер стоит на месте.
export function mapWalk(prevTarget, target) {
  if (prevTarget === null || prevTarget === undefined || prevTarget === "") return null;
  const from = Number(prevTarget);
  const to = Number(target);
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0) return null;
  return to > from ? { from, to } : null;
}

// Размеры сцены и рамка кадра. Нарисованная сцена 1408x470, но блок на странице низкий и широкий
// (на 1280 около 160 px высотой): при обычной обрезке голова голема и его полоска HP уходили за верхний
// край, а на телефоне полоска пряталась под HUD. Поэтому масштаб берём от высоты блока так, чтобы
// полоска HP врага (y = ENEMY_BAR_TOP) оказалась сразу под верхней кромкой (или под HUD на телефоне),
// а по горизонтали сдвигаем кадр: герой правее HUD, враг правее плашки уровня.
export const SCENE_WIDTH = 1408;
export const SCENE_HEIGHT = 470;
export const ENEMY_BAR_TOP = 244;
export const ENEMY_BAR_X = 452;

export function stageView(width, height, hudRight = 0) {
  const w = num(width, 0);
  const h = num(height, 0);
  if (w <= 0 || h <= 0) return { x: 0, y: 0, w: SCENE_WIDTH, h: SCENE_HEIGHT };
  const compact = w < 640;
  // на телефоне HUD это одна строка из двух полосок (~38 px высоты): над полоской врага место под ним
  const reserve = compact ? 44 : 18;
  const scale = Math.max(0.2, (h - reserve) / (SCENE_HEIGHT - ENEMY_BAR_TOP));
  const viewW = w / scale;
  const viewH = h / scale;
  // на телефоне кадр начинается чуть левее героя, чтобы тот не касался края
  let x = HERO_X_MIN - 12 - 16 / scale;
  if (!compact) {
    const pillRight = w / 2 + 100;
    const enemyRightOfPill = ENEMY_BAR_X - pillRight / scale;
    const heroRightOfHud = HERO_X_MIN - 12 - (num(hudRight, 0) + 12) / scale;
    x = Math.min(enemyRightOfPill, heroRightOfHud);
  }
  return { x, y: SCENE_HEIGHT - viewH, w: viewW, h: viewH };
}
