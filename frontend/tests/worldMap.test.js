// Тесты геометрии карты миров (lib/worldMap.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "worldMap.js"), "utf8")
  .replace(/^export /gm, "");
const { mapCoords, mapPath } = new Function(`${source}; return { mapCoords, mapPath };`)();

test("первый узел слева, последний справа, крайние без смещения по x", () => {
  assert.equal(mapCoords(0, 7).x, 8);
  assert.equal(mapCoords(6, 7).x, 80);
  assert.equal(mapCoords(0, 1).x, 8);
});

test("узлы идут слева направо и остаются внутри холста", () => {
  for (const total of [2, 5, 7, 16]) {
    let prevX = -Infinity;
    for (let i = 0; i < total; i++) {
      const { x, y } = mapCoords(i, total);
      assert.ok(x > prevX || total > 7, `x растёт: ${total}/${i}`);
      assert.ok(x >= 0 && x <= 100 && y >= 0 && y <= 100);
      prevX = x;
    }
  }
});

test("тропа: пустая для нуля, один M и по одной кривой на переход", () => {
  assert.equal(mapPath(0), "");
  assert.equal(mapPath(1), "M 8 65");
  const d = mapPath(5);
  assert.ok(d.startsWith("M 8 65"));
  assert.equal((d.match(/C/g) || []).length, 4);
});
