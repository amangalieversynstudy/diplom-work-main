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

/**
 * Фильтр и сортировка. Без sortKey порядок прежний: застрявшие сверху, дальше порядок сервера.
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
    if (!read) return Number(Boolean(y.s?.stuck)) - Number(Boolean(x.s?.stuck)) || x.index - y.index;
    const a = read(x.s);
    const b = read(y.s);
    if (a === null && b === null) return x.index - y.index;
    if (a === null) return 1;
    if (b === null) return -1;
    return sign * compareValues(a, b) || x.index - y.index;
  });
  return list.map((item) => item.s);
}
