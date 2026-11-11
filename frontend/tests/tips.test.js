// Подсказки первого визита (lib/tips.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "..", "lib", "tips.js"), "utf8").replace(/^export /gm, "");
const api = new Function(`${source}; return { tipGroup, readTipState, nextTip, markTipSeen, turnTipsOff, TIP_ORDER };`)();

function memory() {
  const data = {};
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); } };
}

test("tips belong to the map and to missions only", () => {
  assert.equal(api.tipGroup("/worlds"), "map");
  assert.equal(api.tipGroup("/missions/12"), "mission");
  assert.equal(api.tipGroup("/profile"), null);
});

test("each tip is shown once, in order, and remembered", () => {
  const store = memory();
  let id = api.nextTip("map", api.readTipState(store));
  assert.equal(id, "map1");
  api.markTipSeen(store, id);
  id = api.nextTip("map", api.readTipState(store));
  assert.equal(id, "map2");
  api.markTipSeen(store, id);
  assert.equal(api.nextTip("map", api.readTipState(store)), null);
  assert.equal(api.nextTip("mission", api.readTipState(store)), "mission1");
});

test("skipping switches every tip off", () => {
  const store = memory();
  api.turnTipsOff(store);
  assert.equal(api.nextTip("map", api.readTipState(store)), null);
});

test("without storage no tips are shown", () => {
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.equal(api.nextTip("map", api.readTipState(broken)), null);
});
