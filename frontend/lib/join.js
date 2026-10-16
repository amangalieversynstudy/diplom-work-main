// Код класса: как ученик попадает к преподавателю. Файл без импортов (его читает тест как текст).

const KEY = "join_code";

/** Код как его вводят и вставляют: прописные, без пробелов и дефисов. */
export function normalizeJoinCode(value) {
  return String(value ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

/** Запомнить код на время регистрации или входа, чтобы после них вернуться к вступлению. */
export function rememberJoinCode(code) {
  try {
    const clean = normalizeJoinCode(code);
    if (clean) sessionStorage.setItem(KEY, clean);
  } catch {
    // хранилище недоступно (приватное окно): ученик введёт код ещё раз
  }
}

/** Забрать запомненный код (и забыть его). Пустая строка, если кода нет. */
export function takeJoinCode() {
  try {
    const value = sessionStorage.getItem(KEY) || "";
    sessionStorage.removeItem(KEY);
    return normalizeJoinCode(value);
  } catch {
    return "";
  }
}

/** Куда вести после входа или регистрации: во вступление в класс, если код был, иначе туда, куда и вели. */
export function pathAfterAuth(fallback, code) {
  return code ? `/join/${code}` : fallback;
}

/** Ссылка-приглашение для группы. */
export function joinLink(origin, code) {
  return `${String(origin || "").replace(/\/$/, "")}/join/${normalizeJoinCode(code)}`;
}
