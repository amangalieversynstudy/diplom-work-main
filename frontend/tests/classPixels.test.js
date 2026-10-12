// Сетка пиксельных портретов классов: размер, допустимые символы, разные силуэты.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "classPixels.js"), "utf8")
  .replace(/^export /gm, "");
const { PIXEL_SIZE, PIXEL_FILL, PIXEL_ART } = new Function(
  `${source}; return { PIXEL_SIZE, PIXEL_FILL, PIXEL_ART };`,
)();

test("each class has a full square grid of known pixels", () => {
  for (const role of ["python", "django", "devops"]) {
    const rows = PIXEL_ART[role];
    assert.equal(rows.length, PIXEL_SIZE, role);
    for (const row of rows) {
      assert.equal(row.length, PIXEL_SIZE, `${role}: ${row}`);
      for (const ch of row) assert.ok(ch === "." || PIXEL_FILL[ch], `${role}: unknown "${ch}"`);
    }
  }
});

test("classes are visually distinct", () => {
  const joined = ["python", "django", "devops"].map((r) => PIXEL_ART[r].join(""));
  assert.equal(new Set(joined).size, 3);
});

test("palette uses theme tokens only", () => {
  for (const v of Object.values(PIXEL_FILL)) assert.match(v, /^var\(--[a-z-]+\)$/);
});
