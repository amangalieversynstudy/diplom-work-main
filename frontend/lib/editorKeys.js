// Клавиши редактора кода. Для Python отступ — часть синтаксиса, а обычный
// <textarea> уводит Tab на другой элемент страницы. Функции чистые: получают
// текст и выделение, возвращают новый текст и выделение (или null, если клавишу
// нужно оставить браузеру).

export const INDENT = "    ";

const lineStart = (text, index) => text.lastIndexOf("\n", index - 1) + 1;

/** Tab и Shift+Tab. */
export function indentAction(text, start, end, { shift = false } = {}) {
  if (start === end && !shift) {
    // Без выделения: пробелы до ближайшей границы в 4 колонки.
    const column = start - lineStart(text, start);
    const spaces = " ".repeat(INDENT.length - (column % INDENT.length));
    return {
      text: text.slice(0, start) + spaces + text.slice(end),
      start: start + spaces.length,
      end: start + spaces.length,
    };
  }

  // Несколько строк (или Shift+Tab): сдвигаем каждую затронутую строку.
  const first = lineStart(text, start);
  // Выделение, заканчивающееся сразу после перевода строки, эту строку не задевает.
  const lastPoint = end > start && text[end - 1] === "\n" ? end - 1 : end;
  let last = text.indexOf("\n", lastPoint);
  if (last === -1) last = text.length;

  const lines = text.slice(first, last).split("\n");
  const changes = [];
  const shifted = lines.map((line) => {
    if (!shift) {
      changes.push(INDENT.length);
      return INDENT + line;
    }
    const remove = line.startsWith("\t")
      ? 1
      : Math.min(INDENT.length, line.length - line.trimStart().length);
    changes.push(-remove);
    return line.slice(remove);
  });

  const total = changes.reduce((sum, delta) => sum + delta, 0);
  const firstDelta = changes[0];
  return {
    text: text.slice(0, first) + shifted.join("\n") + text.slice(last),
    // начало не уходит левее начала строки; конец сдвигается на все изменения
    start: Math.max(first, start + firstDelta),
    end: Math.max(first, end + total),
  };
}

/** Enter: новая строка с тем же отступом, а после двоеточия ещё на уровень глубже. */
export function newlineAction(text, start, end) {
  const begin = lineStart(text, start);
  const beforeCaret = text.slice(begin, start);
  const leading = beforeCaret.match(/^[ \t]*/)[0];
  const opensBlock = beforeCaret.trimEnd().endsWith(":");
  const inserted = "\n" + leading + (opensBlock ? INDENT : "");
  return {
    text: text.slice(0, start) + inserted + text.slice(end),
    start: start + inserted.length,
    end: start + inserted.length,
  };
}
