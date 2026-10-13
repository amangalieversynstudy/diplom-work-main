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
