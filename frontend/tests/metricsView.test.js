// Карта отсева: клетка с малой выборкой серая, а не ярко-красная (lib/metricsView.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "metricsView.js"), "utf8")
  .replace(/^export /gm, "");
const { heatCellState } = new Function(`${source}; return { heatCellState };`)();

test("one learner who left is not a bright red 100%", () => {
  const cell = heatCellState({ opened: 1, known: 1, dropout_rate: 100 }, 5);
  assert.equal(cell.state, "few");
  assert.equal(cell.rate, null);
  assert.equal(cell.text, "n=1");
});

test("enough known outcomes show the percentage", () => {
  const cell = heatCellState({ opened: 9, known: 8, dropout_rate: 37.5 }, 5);
  assert.deepEqual(cell, { state: "ok", text: "38%", rate: 37.5 });
});

test("a step nobody opened stays an empty dot, and pairs still in progress do not count", () => {
  assert.equal(heatCellState({ opened: 0, known: 0, dropout_rate: null }, 5).state, "empty");
  assert.equal(heatCellState({ opened: 30, known: 2, dropout_rate: 50 }, 5).state, "few");
});

const { kpiState } = new Function(`${source}; return { kpiState };`)();

test("a KPI tile on a tiny sample says too little data", () => {
  assert.deepEqual(kpiState(1, 5), { few: true, n: 1 });
  assert.deepEqual(kpiState(undefined, 5), { few: true, n: 0 });
});

test("a KPI tile with enough known outcomes shows the number", () => {
  assert.equal(kpiState(5, 5).few, false);
  assert.equal(kpiState(40, 5).few, false);
});

const { splitEmptyMissions, dailyTotals } = new Function(`${source}; return { splitEmptyMissions, dailyTotals };`)();

test("missions nobody opened are split off from the ones with data", () => {
  const missions = [
    { id: 1, steps: [{ opened: 3 }, { opened: 0 }] },
    { id: 2, steps: [{ opened: 0 }, { opened: 0 }] },
    { id: 3, steps: [] },
  ];
  const { shown, hidden } = splitEmptyMissions(missions);
  assert.deepEqual(shown.map((m) => m.id), [1]);
  assert.deepEqual(hidden.map((m) => m.id), [2, 3]);
  assert.deepEqual(splitEmptyMissions(undefined), { shown: [], hidden: [] });
});

test("daily totals give the scale of the chart and say when nothing happened", () => {
  const totals = dailyTotals([
    { active: 2, solved: 1, runs: 4 },
    { active: 5, solved: 3, runs: 0 },
  ]);
  assert.deepEqual(totals, { days: 2, peak: 5, solved: 4, runs: 4, maxSolved: 3, empty: false });
  assert.equal(dailyTotals([{ active: 0, solved: 0, runs: 0 }]).empty, true);
  assert.equal(dailyTotals(null).empty, true);
});
