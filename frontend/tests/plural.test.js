// Тесты русских и английских форм числительных (lib/plural.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "plural.js"), "utf8")
  .replace(/^export /gm, "");
const { pluralCategory, unit } = new Function(`${source}; return { pluralCategory, unit };`)();

test("Russian: 1, 21, 101 take the singular", () => {
  for (const n of [1, 21, 101, 1001]) assert.equal(pluralCategory(n, "ru"), "one", String(n));
});

test("Russian: 2-4, 22-24, 102 take the paucal", () => {
  for (const n of [2, 3, 4, 22, 23, 24, 102]) assert.equal(pluralCategory(n, "ru"), "few", String(n));
});

test("Russian: 0, 5-20, 25-30, 111-114 take the plural", () => {
  for (const n of [0, 5, 9, 10, 11, 12, 13, 14, 15, 20, 25, 30, 100, 111, 112, 114]) {
    assert.equal(pluralCategory(n, "ru"), "many", String(n));
  }
});

test("English has only one and many", () => {
  assert.equal(pluralCategory(1, "en"), "one");
  for (const n of [0, 2, 5, 21]) assert.equal(pluralCategory(n, "en"), "many", String(n));
});

test("junk input is treated as zero, not as a crash", () => {
  assert.equal(pluralCategory(undefined, "ru"), "many");
  assert.equal(pluralCategory("abc", "ru"), "many");
  assert.equal(pluralCategory(-1, "ru"), "one");
});

test("unit picks the dictionary key for the form", () => {
  const words = { "units.student_one": "ученик", "units.student_few": "ученика", "units.student_many": "учеников" };
  const t = (key) => words[key];
  assert.equal(unit(t, "ru", "student", 1), "ученик");
  assert.equal(unit(t, "ru", "student", 24), "ученика");
  assert.equal(unit(t, "ru", "student", 30), "учеников");
});
