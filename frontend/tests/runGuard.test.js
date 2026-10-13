// Защита от двойного щелчка по «Запустить» (lib/runGuard.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "runGuard.js"), "utf8")
  .replace(/^export /gm, "");
const { isAccidentalStop, STOP_GUARD_MS } = new Function(
  `${source}; return { isAccidentalStop, STOP_GUARD_MS };`
)();

test("a click right after the start is a double click, not a stop", () => {
  assert.equal(isAccidentalStop(1000, 1100), true);
});

test("a click after the guard window stops the run", () => {
  assert.equal(isAccidentalStop(1000, 1000 + STOP_GUARD_MS), false);
  assert.equal(isAccidentalStop(1000, 5000), false);
});
