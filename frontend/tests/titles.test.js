// Тесты титулов (lib/titles.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "titles.js"), "utf8")
  .replace(/^export /gm, "");
const { titleFor } = new Function(`${source}; return { titleFor };`)();

test("граничные уровни звания", () => {
  const rank = (level) => titleFor(level, []).rank;
  assert.equal(rank(1), "novice");
  assert.equal(rank(2), "apprentice");
  assert.equal(rank(4), "apprentice");
  assert.equal(rank(5), "mage");
  assert.equal(rank(9), "mage");
  assert.equal(rank(10), "archmage");
  assert.equal(rank(19), "archmage");
  assert.equal(rank(20), "grandWizard");
  assert.equal(rank(99), "grandWizard");
});

test("мусорный уровень даёт новичка", () => {
  for (const bad of [0, -3, null, undefined, "x", NaN]) assert.equal(titleFor(bad, []).rank, "novice");
});

test("пустые и отсутствующие достижения не дают эпитета", () => {
  assert.equal(titleFor(5, []).badge, null);
  assert.equal(titleFor(5, undefined).badge, null);
  assert.equal(titleFor(5, null).badge, null);
});

test("эпитет — самое весомое открытое достижение", () => {
  const items = [
    { slug: "five_missions", earned: true },
    { slug: "streak_7", earned: true },
    { slug: "track_complete", earned: false },
  ];
  assert.equal(titleFor(3, items).badge, "streak_7");
  assert.equal(titleFor(3, ["five_missions", "track_complete"]).badge, "track_complete");
});

test("first_mission и level_5 эпитета не дают", () => {
  assert.equal(titleFor(5, ["first_mission", "level_5"]).badge, null);
});
