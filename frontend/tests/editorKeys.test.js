// Тесты клавиш редактора. lib/editorKeys.js написан как ES-модуль без импортов,
// поэтому загружаем его исходник без сборщика.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "editorKeys.js"), "utf8")
  .replace(/^export /gm, "");
const { indentAction, newlineAction, INDENT } = new Function(
  `${source}; return { indentAction, newlineAction, INDENT };`
)();

test("Tab without a selection pads to the next 4-column stop", () => {
  const result = indentAction("ab", 2, 2);
  assert.equal(result.text, "ab  ");
  assert.equal(result.start, 4);
  assert.equal(result.end, 4);
});

test("Tab at the start of a line inserts a full indent", () => {
  assert.equal(indentAction("x = 1", 0, 0).text, INDENT + "x = 1");
});

test("Tab over several lines indents each of them and keeps the selection", () => {
  const text = "a\nb\nc";
  const result = indentAction(text, 0, text.length);
  assert.equal(result.text, "    a\n    b\n    c");
  // the selection keeps covering the same characters, so both ends move with the text
  assert.equal(result.start, 4);
  assert.equal(result.end, text.length + 12);
});

test("a selection that ends right after a newline leaves that last line alone", () => {
  const text = "a\nb\n";
  const result = indentAction(text, 0, 4);
  assert.equal(result.text, "    a\n    b\n");
});

test("Shift+Tab removes at most one indent level and never eats text", () => {
  assert.equal(indentAction("        x", 0, 0, { shift: true }).text, "    x");
  assert.equal(indentAction("  x", 0, 0, { shift: true }).text, "x");
  assert.equal(indentAction("x", 0, 0, { shift: true }).text, "x");
});

test("Shift+Tab removes a tab character as one level", () => {
  assert.equal(indentAction("\tx", 1, 1, { shift: true }).text, "x");
});

test("Enter keeps the indentation of the current line", () => {
  const result = newlineAction("    x = 1", 9, 9);
  assert.equal(result.text, "    x = 1\n    ");
  assert.equal(result.start, result.text.length);
});

test("Enter after a colon opens a deeper block", () => {
  const result = newlineAction("def f():", 8, 8);
  assert.equal(result.text, "def f():\n    ");
});

test("Enter after a colon inside an indented block adds one more level", () => {
  const result = newlineAction("    if x:", 9, 9);
  assert.equal(result.text, "    if x:\n        ");
});

test("Enter replaces a selection with the new line", () => {
  const result = newlineAction("ab", 0, 2);
  assert.equal(result.text, "\n");
});
