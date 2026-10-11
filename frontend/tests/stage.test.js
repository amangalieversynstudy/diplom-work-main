// Тесты чистых функций сцены (lib/stage.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "stage.js"), "utf8")
  .replace(/^export /gm, "");
const api = new Function(
  `${source}; return { HERO_X_MIN, HERO_X_MAX, ENEMY_HUES, heroXForStep, enemyHpFromProgress, solvedCount, heroHpAfter, mpAfter, enemyHueForMission, mapWalk };`
)();
const {
  HERO_X_MIN,
  HERO_X_MAX,
  ENEMY_HUES,
  heroXForStep,
  enemyHpFromProgress,
  solvedCount,
  heroHpAfter,
  mpAfter,
  enemyHueForMission,
  mapWalk,
} = api;

test("heroXForStep: first step at the left edge, last step in front of the enemy", () => {
  assert.equal(heroXForStep(0, 5), HERO_X_MIN);
  assert.equal(heroXForStep(4, 5), HERO_X_MAX);
  assert.equal(heroXForStep(2, 5), (HERO_X_MIN + HERO_X_MAX) / 2);
});

test("heroXForStep: the hero only moves forward", () => {
  let last = -Infinity;
  for (let i = 0; i < 7; i += 1) {
    const x = heroXForStep(i, 7);
    assert.ok(x > last, `step ${i}`);
    last = x;
  }
});

test("heroXForStep: zero or one step stays at the start, out-of-range indices are clamped", () => {
  assert.equal(heroXForStep(0, 0), HERO_X_MIN);
  assert.equal(heroXForStep(0, 1), HERO_X_MIN);
  assert.equal(heroXForStep(-1, 1), HERO_X_MIN);
  assert.equal(heroXForStep(-3, 4), HERO_X_MIN);
  assert.equal(heroXForStep(99, 4), HERO_X_MAX);
  assert.equal(heroXForStep(undefined, 4), HERO_X_MIN);
  assert.equal(heroXForStep(1, undefined), HERO_X_MIN);
});

test("enemyHpFromProgress: full at the start, empty when everything is solved", () => {
  assert.equal(enemyHpFromProgress(0, 4), 100);
  assert.equal(enemyHpFromProgress(1, 4), 75);
  assert.equal(enemyHpFromProgress(4, 4), 0);
  assert.equal(enemyHpFromProgress(1, 1), 0);
});

test("enemyHpFromProgress: no steps leaves the enemy untouched, bad input is clamped", () => {
  assert.equal(enemyHpFromProgress(0, 0), 100);
  assert.equal(enemyHpFromProgress(3, 0), 100);
  assert.equal(enemyHpFromProgress(9, 4), 0);
  assert.equal(enemyHpFromProgress(-2, 4), 100);
  assert.equal(enemyHpFromProgress(undefined, 4), 100);
});

test("solvedCount: counts only completed steps of this mission", () => {
  const tasks = [{ id: 1 }, { id: 2 }, { id: 3 }];
  const progress = { 1: { status: "completed" }, 2: { status: "in_progress" }, 9: { status: "completed" } };
  assert.equal(solvedCount(tasks, progress), 1);
  assert.equal(solvedCount([], progress), 0);
  assert.equal(solvedCount(tasks, {}), 0);
  assert.equal(solvedCount(null, progress), 0);
});

test("heroHpAfter: a failure takes 10 %, success and a new step restore", () => {
  assert.equal(heroHpAfter(100, "failure"), 90);
  assert.equal(heroHpAfter(90, "failure"), 80);
  assert.equal(heroHpAfter(70, "success"), 100);
  assert.equal(heroHpAfter(60, "step"), 100);
});

test("heroHpAfter: repeated failures stop at the 50 % floor", () => {
  let hp = 100;
  for (let i = 0; i < 12; i += 1) hp = heroHpAfter(hp, "failure");
  assert.equal(hp, 50);
  assert.equal(heroHpAfter(50, "failure"), 50);
  assert.equal(heroHpAfter(55, "failure"), 50);
});

test("heroHpAfter: unknown events and bad values do not break the bar", () => {
  assert.equal(heroHpAfter(80, "something"), 80);
  assert.equal(heroHpAfter(undefined, "failure"), 90);
  assert.equal(heroHpAfter(NaN, "step"), 100);
  assert.equal(heroHpAfter(40, "failure"), 40);
});

test("mpAfter: every attempt costs 20 %, never below 20 %", () => {
  assert.equal(mpAfter(100, "attempt"), 80);
  assert.equal(mpAfter(80, "attempt"), 60);
  let mp = 100;
  for (let i = 0; i < 10; i += 1) mp = mpAfter(mp, "attempt");
  assert.equal(mp, 20);
  assert.equal(mpAfter(20, "attempt"), 20);
});

test("mpAfter: a new step refills, other events change nothing", () => {
  assert.equal(mpAfter(20, "step"), 100);
  assert.equal(mpAfter(60, "success"), 60);
  assert.equal(mpAfter(undefined, "attempt"), 80);
});

test("enemyHueForMission: stable per mission, cycles through the palette", () => {
  assert.equal(enemyHueForMission(0), ENEMY_HUES[0]);
  assert.equal(enemyHueForMission(1), ENEMY_HUES[1]);
  assert.equal(enemyHueForMission(1), enemyHueForMission(1));
  assert.equal(enemyHueForMission(ENEMY_HUES.length + 2), ENEMY_HUES[2]);
  assert.equal(enemyHueForMission(-1), ENEMY_HUES[ENEMY_HUES.length - 1]);
  assert.equal(enemyHueForMission("3"), ENEMY_HUES[3]);
  assert.equal(enemyHueForMission(undefined), ENEMY_HUES[0]);
});

test("mapWalk: walks only forward from a remembered node", () => {
  assert.deepEqual(mapWalk(2, 3), { from: 2, to: 3 });
  assert.deepEqual(mapWalk(0, 4), { from: 0, to: 4 });
  assert.deepEqual(mapWalk("1", 2), { from: 1, to: 2 });
});

test("mapWalk: no memory, no change or a step back means no walk", () => {
  assert.equal(mapWalk(null, 3), null);
  assert.equal(mapWalk(undefined, 3), null);
  assert.equal(mapWalk("", 3), null);
  assert.equal(mapWalk(3, 3), null);
  assert.equal(mapWalk(4, 2), null);
  assert.equal(mapWalk("abc", 2), null);
  assert.equal(mapWalk(1, NaN), null);
  assert.equal(mapWalk(-1, 2), null);
});
