// Определяет тип первой ошибки Python в тексте stderr, чтобы Мудрец коротко объяснил её по-русски.
// Сам вывод терминала не меняется: пояснение печатается отдельно, под выводом.

export const ERROR_TYPES = [
  "SyntaxError",
  "IndentationError",
  "NameError",
  "TypeError",
  "ZeroDivisionError",
  "ValueError",
  "IndexError",
  "KeyError",
  "AttributeError",
  "ImportError",
];

// Наследники, которые ученик видит под своим именем, но объясняются как родитель.
const ALIASES = {
  TabError: "IndentationError",
  UnboundLocalError: "NameError",
  ModuleNotFoundError: "ImportError",
};

// eslint-disable-next-line no-control-regex
const ANSI = /\u001b\[[0-9;]*[A-Za-z]/g;
const ERROR_LINE = /^\s*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning))\b\s*(?::|$)/;

/**
 * Возвращает тип ошибки из списка ERROR_TYPES или null, если ошибка не из списка.
 * Берётся первая строка вида «ТипОшибки: сообщение»; строки внутри traceback
 * (в них нет двоеточия сразу после имени) пропускаются.
 */
export function detectErrorType(text) {
  if (typeof text !== "string" || !text) return null;
  const lines = text.replace(ANSI, "").split(/\r?\n/);
  for (const line of lines) {
    const m = ERROR_LINE.exec(line);
    if (!m) continue;
    const name = ALIASES[m[1]] || m[1];
    return ERROR_TYPES.includes(name) ? name : null;
  }
  return null;
}
