// Тесты поиска и сортировки таблицы учеников (lib/students.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "students.js"), "utf8")
  .replace(/^export /gm, "");
const { filterAndSortStudents, matchesQuery } = new Function(
  `${source}; return { filterAndSortStudents, matchesQuery };`
)();

const rows = [
  { id: 1, username: "demo_01", display_name: "Алия", xp: 100, completed_count: 3, last_active: "2026-10-10T10:00:00Z", stuck: false },
  { id: 2, username: "demo_02", display_name: "борис", xp: 100, completed_count: 5, last_active: "2026-10-12T10:00:00Z", stuck: true },
  { id: 3, username: "Demo_03", display_name: "", xp: null, completed_count: 0, last_active: null, stuck: false },
  { id: 4, username: "demo_04", display_name: "Ерсін", xp: 250, completed_count: 5, last_active: "2026-10-11T10:00:00Z", stuck: false },
];
const ids = (list) => list.map((s) => s.id);

test("empty query keeps everyone, stuck first, server order otherwise", () => {
  assert.deepEqual(ids(filterAndSortStudents(rows, { query: "  " })), [2, 1, 3, 4]);
  assert.deepEqual(ids(filterAndSortStudents(rows)), [2, 1, 3, 4]);
});

test("search ignores case and works on Cyrillic", () => {
  assert.deepEqual(ids(filterAndSortStudents(rows, { query: "АЛИЯ" })), [1]);
  assert.deepEqual(ids(filterAndSortStudents(rows, { query: "Борис" })), [2]);
  assert.deepEqual(ids(filterAndSortStudents(rows, { query: "ерс" })), [4]);
});

test("search also matches the login, including when there is no display name", () => {
  assert.deepEqual(ids(filterAndSortStudents(rows, { query: "demo_03" })), [3]);
  assert.equal(matchesQuery({ username: "x" }, "y"), false);
  assert.deepEqual(filterAndSortStudents(rows, { query: "нет такого" }), []);
});

test("sort by xp desc is stable and puts empty values last", () => {
  assert.deepEqual(ids(filterAndSortStudents(rows, { sortKey: "xp", direction: "desc" })), [4, 1, 2, 3]);
  assert.deepEqual(ids(filterAndSortStudents(rows, { sortKey: "xp", direction: "asc" })), [1, 2, 4, 3]);
});

test("sort by last activity: never active is always last", () => {
  assert.deepEqual(ids(filterAndSortStudents(rows, { sortKey: "lastActive", direction: "desc" })), [2, 4, 1, 3]);
  assert.deepEqual(ids(filterAndSortStudents(rows, { sortKey: "lastActive", direction: "asc" })), [1, 4, 2, 3]);
});

test("sort by name uses Russian collation and the login as fallback", () => {
  const named = rows.filter((s) => s.display_name);
  assert.deepEqual(ids(filterAndSortStudents(named, { sortKey: "name", direction: "asc" })), [1, 2, 4]);
  assert.deepEqual(ids(filterAndSortStudents(named, { sortKey: "name", direction: "desc" })), [4, 2, 1]);
  assert.equal(filterAndSortStudents(rows, { sortKey: "name", direction: "asc" }).length, 4);
});

test("sort by completed ties keep the original order; input is not mutated", () => {
  const copy = JSON.stringify(rows);
  assert.deepEqual(ids(filterAndSortStudents(rows, { sortKey: "completed", direction: "desc" })), [2, 4, 1, 3]);
  assert.equal(JSON.stringify(rows), copy);
});

test("non-array input gives an empty list", () => {
  assert.deepEqual(filterAndSortStudents(undefined, { query: "a" }), []);
});

// ── пустой список «Кому нужна помощь» ───────────────────────────────────────

const emptySource = fs
  .readFileSync(path.join(__dirname, "..", "lib", "students.js"), "utf8")
  .replace(/^export /gm, "");
const { warningEmptyState } = new Function(`${emptySource}; return { warningEmptyState };`)();

test("an empty warning list is 'all clear' only when there is data behind it", () => {
  assert.equal(warningEmptyState({ total: 0, with_activity: 0 }), "noStudents");
  assert.equal(warningEmptyState({ total: 12, with_activity: 0 }), "noData");
  assert.equal(warningEmptyState({ total: 12, with_activity: 3 }), "clear");
  assert.equal(warningEmptyState(undefined), "noStudents");
});
