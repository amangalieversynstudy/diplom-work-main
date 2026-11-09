// Тесты разбора текста сюжета миссии (lib/story.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "story.js"), "utf8")
  .replace(/^export /gm, "");
const { parseStory, storyToHtml, isHtmlBody } = new Function(
  `${source}; return { parseStory, storyToHtml, isHtmlBody };`
)();

test("blank lines split plain text into paragraphs", () => {
  const blocks = parseStory("Первый абзац.\n\nВторой абзац\nс переносом.");
  assert.deepEqual(blocks, [
    { type: "p", text: "Первый абзац." },
    { type: "p", text: "Второй абзац\nс переносом." },
  ]);
});

test("fenced code becomes a code block and keeps its inner blank lines", () => {
  const blocks = parseStory("Смотри:\n```python\nx = 1\n\nprint(x)\n```\nГотово.");
  assert.deepEqual(blocks, [
    { type: "p", text: "Смотри:" },
    { type: "code", text: "x = 1\n\nprint(x)" },
    { type: "p", text: "Готово." },
  ]);
});

test("an unclosed fence runs to the end of the text", () => {
  assert.deepEqual(parseStory("```\na = 1\nb = 2"), [{ type: "code", text: "a = 1\nb = 2" }]);
});

test("four-space and tab indentation make a code block", () => {
  const blocks = parseStory("Пример:\n\n    hero = 'Ли'\n\n    power = 42\n\nКонец.");
  assert.deepEqual(blocks, [
    { type: "p", text: "Пример:" },
    { type: "code", text: "hero = 'Ли'\n\npower = 42" },
    { type: "p", text: "Конец." },
  ]);
  assert.deepEqual(parseStory("\tprint(1)"), [{ type: "code", text: "print(1)" }]);
});

test("CRLF line endings and empty input are handled", () => {
  assert.deepEqual(parseStory("а\r\n\r\nб"), [
    { type: "p", text: "а" },
    { type: "p", text: "б" },
  ]);
  assert.deepEqual(parseStory(""), []);
  assert.deepEqual(parseStory(null), []);
});

test("plain text is rendered as escaped paragraphs, pre blocks and inline code", () => {
  const html = storyToHtml("Используй `print` и <b>теги</b>.\n\n```\nif a < b:\n    pass\n```");
  assert.equal(
    html,
    "<p>Используй <code>print</code> и &lt;b&gt;теги&lt;/b&gt;.</p>" +
      "<pre><code>if a &lt; b:\n    pass</code></pre>"
  );
});

test("a lesson typed as plain text gets headings, lists, notes, bold and links", () => {
  const text = [
    "## Что узнаем",
    "Как программа **выбирает**:",
    "- условие `if`",
    "- ветка `else`",
    "",
    "1. прочитай пример",
    "2) запусти его",
    "",
    "Важно: после условия ставится двоеточие,",
    "а блок сдвигается на 4 пробела.",
    "",
    "> Код — это заклинание.",
    "",
    "Подробнее: [документация](https://docs.python.org/3/) и [не ссылка](javascript:alert(1)).",
  ].join("\n");
  assert.equal(
    storyToHtml(text),
    "<h3>Что узнаем</h3>" +
      "<p>Как программа <strong>выбирает</strong>:</p>" +
      "<ul><li>условие <code>if</code></li><li>ветка <code>else</code></li></ul>" +
      "<ol><li>прочитай пример</li><li>запусти его</li></ol>" +
      "<blockquote><strong>Важно:</strong> после условия ставится двоеточие,<br>а блок сдвигается на 4 пробела.</blockquote>" +
      "<blockquote>Код — это заклинание.</blockquote>" +
      '<p>Подробнее: <a href="https://docs.python.org/3/">документация</a> и [не ссылка](javascript:alert(1)).</p>'
  );
});

test("markup inside code stays code, and a list item may continue on the next line", () => {
  assert.equal(storyToHtml("`**не жирный**`"), "<p><code>**не жирный**</code></p>");
  assert.deepEqual(parseStory("- первый пункт\n  продолжение\n- второй"), [
    { type: "ul", items: ["первый пункт\nпродолжение", "второй"] },
  ]);
  // комментарий внутри кода с отступом не становится заголовком
  assert.deepEqual(parseStory("    # шаг 1\n    x = 1"), [{ type: "code", text: "# шаг 1\nx = 1" }]);
});

test("ready HTML from the teacher is returned unchanged", () => {
  const html = "<h2>Заголовок</h2><p>Текст</p><pre><code>x = 1</code></pre>";
  assert.equal(isHtmlBody(html), true);
  assert.equal(storyToHtml(html), html);
  assert.equal(storyToHtml("   "), "");
});
