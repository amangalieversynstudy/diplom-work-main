// Поиск и сортировка таблицы учеников в кабинете преподавателя. Чистые функции поверх уже
// загруженного списка: без запросов к серверу и без изменения самих данных.

const LOCALE = "ru";

/** Имя для показа и поиска: display_name, а если его нет, логин. */
export function studentName(student) {
  return String(student?.display_name || student?.username || "");
}

/** Совпадает ли ученик с запросом: по имени и логину, без учёта регистра и пробелов по краям. */
export function matchesQuery(student, query) {
  const needle = String(query ?? "").trim().toLocaleLowerCase(LOCALE);
  if (!needle) return true;
  const haystack = `${student?.display_name || ""} ${student?.username || ""}`.toLocaleLowerCase(LOCALE);
  return haystack.includes(needle);
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function timeOrNull(value) {
  if (!value) return null;
  const ts = new Date(value).getTime();
  return Number.isNaN(ts) ? null : ts;
}

/**
 * Что сказать, когда список «Кому нужна помощь» пуст. «Никому не нужна помощь» честно только тогда,
 * когда за этим есть данные: ученики есть и хоть кто-то что-то делал. Иначе пустой список означает
 * «проверять некого» или «данных пока нет».
 * @returns {"noStudents" | "noData" | "clear"}
 */
export function warningEmptyState(summary) {
  const total = Number(summary?.total) || 0;
  if (total === 0) return "noStudents";
  if (!(Number(summary?.with_activity) > 0)) return "noData";
  return "clear";
}

export const SORT_KEYS = ["name", "xp", "completed", "lastActive"];

// Значение для сравнения; null означает «нет данных» и всегда уходит в конец.
const READERS = {
  name: (s) => (studentName(s) ? studentName(s).toLocaleLowerCase(LOCALE) : null),
  xp: (s) => numberOrNull(s?.xp),
  completed: (s) => numberOrNull(s?.completed_count),
  lastActive: (s) => timeOrNull(s?.last_active),
};

function compareValues(a, b) {
  if (typeof a === "string") return a.localeCompare(b, LOCALE);
  return a - b;
}

const LEVEL_RANK = { high: 0, medium: 1 };

/** Насколько срочно: 0 «срочно», 1 «внимание», 2 «в норме». Без warning_level работает старое поле stuck. */
export function urgencyRank(student) {
  const rank = LEVEL_RANK[student?.warning_level];
  if (rank !== undefined) return rank;
  return student?.stuck ? 1 : 2;
}

/**
 * Фильтр и сортировка. Без sortKey: сначала срочные, затем внимание, затем остальные; внутри групп порядок сервера.
 * Сортировка устойчива: при равных значениях сохраняется исходный порядок, пустые значения
 * идут в конце при любом направлении.
 */
export function filterAndSortStudents(students, { query = "", sortKey = null, direction = "desc" } = {}) {
  const list = (Array.isArray(students) ? students : [])
    .filter((s) => matchesQuery(s, query))
    .map((s, index) => ({ s, index }));
  const read = READERS[sortKey];
  const sign = direction === "asc" ? 1 : -1;
  list.sort((x, y) => {
    if (!read) return urgencyRank(x.s) - urgencyRank(y.s) || x.index - y.index;
    const a = read(x.s);
    const b = read(y.s);
    if (a === null && b === null) return x.index - y.index;
    if (a === null) return 1;
    if (b === null) return -1;
    return sign * compareValues(a, b) || x.index - y.index;
  });
  return list.map((item) => item.s);
}
