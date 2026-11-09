// Разбор текста урока (сюжет, теория, условие задачи) в блоки. Чистые функции без React и DOM,
// поэтому их проверяют тесты node --test (tests/story.test.js).
//
// Тело шага приходит либо готовым HTML (встроенные курсы; тогда его не трогаем), либо простым текстом,
// который преподаватель пишет без всякой разметки:
//   пустая строка — новый абзац;            # / ## / ### Заголовок — заголовок;
//   - пункт, * пункт, • пункт — список;      1. пункт или 1) пункт — нумерованный список;
//   Важно: / Совет: / Запомни: … — заметка;  > текст — цитата;
//   **жирный**, `код`, [текст](https://…) — внутри строки;
//   код — в ограждении ``` или с отступом 4 пробела (табуляция).

const BLOCK_HTML = /<(?:p|pre|h[1-6]|ul|ol|li|table|blockquote|div|br|hr)\b/i;
const INDENTED = /^(?: {4}|\t)/;
const FENCE = /^\s*```(.*)$/;
const HEADING = /^(#{1,3})\s+(.+)$/;
const BULLET = /^\s{0,3}[-*•]\s+(.+)$/;
const NUMBERED = /^\s{0,3}\d{1,3}[.)]\s+(.+)$/;
const CONTINUATION = /^\s{2,}\S/;
const NOTE = /^(Важно|Внимание|Совет|Запомни|Подсказка|Note|Tip|Important|Warning)\s*:\s*(.*)$/i;
const QUOTE = /^>\s?(.*)$/;

export function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function isHtmlBody(text) {
  return BLOCK_HTML.test(String(text || ""));
}

// Возвращает список блоков: { type: "p", text }, { type: "code", text }, { type: "h", level, text },
// { type: "ul" | "ol", items }, { type: "note", label, text }.
export function parseStory(text) {
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let para = [];
  let code = null; // накопитель блока с отступом
  let fence = null; // накопитель блока в ограждении ```
  let list = null; // { type: "ul" | "ol", items }
  let note = null; // { label, lines }

  const flushPara = () => {
    if (para.length) blocks.push({ type: "p", text: para.join("\n") });
    para = [];
  };
  const flushCode = () => {
    if (code) {
      while (code.length && !code[code.length - 1].trim()) code.pop();
      if (code.length) blocks.push({ type: "code", text: code.join("\n") });
    }
    code = null;
  };
  const flushList = () => {
    if (list && list.items.length) blocks.push(list);
    list = null;
  };
  const flushNote = () => {
    if (note) blocks.push({ type: "note", label: note.label, text: note.lines.join("\n") });
    note = null;
  };
  const flushText = () => {
    flushPara();
    flushList();
    flushNote();
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    if (fence) {
      if (FENCE.test(line) && !FENCE.exec(line)[1].trim()) {
        if (fence.length) blocks.push({ type: "code", text: fence.join("\n") });
        fence = null;
      } else {
        fence.push(line);
      }
      continue;
    }

    if (FENCE.test(line)) {
      flushText();
      flushCode();
      fence = [];
      continue;
    }

    if (!line.trim()) {
      flushText();
      // пустая строка внутри кода с отступом допустима, если дальше код продолжается
      if (code) {
        const next = lines.slice(i + 1).find((l) => l.trim());
        if (next !== undefined && INDENTED.test(next)) code.push("");
        else flushCode();
      }
      continue;
    }

    if (INDENTED.test(line) && !para.length && !list && !note) {
      if (!code) code = [];
      code.push(line.replace(INDENTED, ""));
      continue;
    }

    flushCode();

    const heading = HEADING.exec(line);
    if (heading) {
      flushText();
      blocks.push({ type: "h", level: heading[1].length, text: heading[2].trim() });
      continue;
    }

    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    if (bullet || numbered) {
      flushPara();
      flushNote();
      const type = bullet ? "ul" : "ol";
      if (list && list.type !== type) flushList();
      if (!list) list = { type, items: [] };
      list.items.push((bullet || numbered)[1].trim());
      continue;
    }
    if (list && CONTINUATION.test(line)) {
      list.items[list.items.length - 1] += `\n${line.trim()}`;
      continue;
    }
    flushList();

    const quote = QUOTE.exec(line);
    const noteStart = !para.length && !note ? NOTE.exec(line.trim()) : null;
    if (noteStart || (quote && !para.length)) {
      flushNote();
      note = noteStart
        ? { label: noteStart[1], lines: noteStart[2] ? [noteStart[2]] : [] }
        : { label: "", lines: [quote[1]] };
      continue;
    }
    if (note) {
      note.lines.push(quote ? quote[1] : line.trim());
      continue;
    }

    para.push(line.trim());
  }

  if (fence && fence.length) blocks.push({ type: "code", text: fence.join("\n") });
  flushText();
  flushCode();
  return blocks;
}

// Разметка внутри строки: `код` защищён от остального, затем **жирный** и ссылки только по http(s).
function inline(text) {
  return String(text)
    .split(/(`[^`\n]+`)/g)
    .map((part) => {
      if (/^`[^`\n]+`$/.test(part)) return `<code>${escapeHtml(part.slice(1, -1))}</code>`;
      return escapeHtml(part)
        .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>')
        .replace(/\n/g, "<br>");
    })
    .join("");
}

function renderBlock(block) {
  switch (block.type) {
    case "code":
      return `<pre><code>${escapeHtml(block.text)}</code></pre>`;
    case "h": {
      const tag = `h${Math.min(block.level + 1, 4)}`;
      return `<${tag}>${inline(block.text)}</${tag}>`;
    }
    case "ul":
    case "ol":
      return `<${block.type}>${block.items.map((item) => `<li>${inline(item)}</li>`).join("")}</${block.type}>`;
    case "note":
      return `<blockquote>${block.label ? `<strong>${escapeHtml(block.label)}:</strong> ` : ""}${inline(block.text)}</blockquote>`;
    default:
      return `<p>${inline(block.text)}</p>`;
  }
}

// HTML для вывода: готовую разметку возвращает как есть, простой текст раскладывает на блоки.
export function storyToHtml(text) {
  const raw = String(text || "");
  if (!raw.trim()) return "";
  if (isHtmlBody(raw)) return raw;
  return parseStory(raw).map(renderBlock).join("");
}
