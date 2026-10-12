// Разбор текста сюжета миссии в абзацы и блоки кода. Чистые функции без React и DOM,
// поэтому их проверяют тесты node --test (tests/story.test.js).
//
// Тело шага приходит либо готовым HTML от преподавателя (тогда его не трогаем),
// либо простым текстом: абзацы разделены пустой строкой, код стоит в ограждении ```
// или набран с отступом (4 пробела либо табуляция).

const BLOCK_HTML = /<(?:p|pre|h[1-6]|ul|ol|li|table|blockquote|div|br|hr)\b/i;
const INDENTED = /^(?: {4}|\t)/;
const FENCE = /^\s*```(.*)$/;

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

// Возвращает список блоков: { type: "p", text } или { type: "code", text }.
export function parseStory(text) {
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let para = [];
  let code = null; // накопитель блока с отступом
  let fence = null; // накопитель блока в ограждении ```

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
      flushPara();
      flushCode();
      fence = [];
      continue;
    }

    if (!line.trim()) {
      flushPara();
      // пустая строка внутри кода с отступом допустима, если дальше код продолжается
      if (code) {
        const next = lines.slice(i + 1).find((l) => l.trim());
        if (next !== undefined && INDENTED.test(next)) code.push("");
        else flushCode();
      }
      continue;
    }

    if (INDENTED.test(line) && !para.length) {
      if (!code) code = [];
      code.push(line.replace(INDENTED, ""));
      continue;
    }

    flushCode();
    para.push(line.trim());
  }

  if (fence && fence.length) blocks.push({ type: "code", text: fence.join("\n") });
  flushPara();
  flushCode();
  return blocks;
}

function inline(text) {
  return escapeHtml(text)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

// HTML для вывода: готовую разметку возвращает как есть, простой текст раскладывает на блоки.
export function storyToHtml(text) {
  const raw = String(text || "");
  if (!raw.trim()) return "";
  if (isHtmlBody(raw)) return raw;
  return parseStory(raw)
    .map((block) =>
      block.type === "code"
        ? `<pre><code>${escapeHtml(block.text)}</code></pre>`
        : `<p>${inline(block.text)}</p>`
    )
    .join("");
}
