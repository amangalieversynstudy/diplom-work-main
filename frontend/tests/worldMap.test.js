// Тесты геометрии карты миров (lib/worldMap.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "worldMap.js"), "utf8")
  .replace(/^export /gm, "");
const { mapCoords, mapPath, mapLandmarks, mapRegions, worldFor, WORLDS, DEFAULT_WORLD } = new Function(
  `${source}; return { mapCoords, mapPath, mapLandmarks, mapRegions, worldFor, WORLDS, DEFAULT_WORLD };`
)();

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

test("у каждого класса свой мир, без класса — общий атлас", () => {
  assert.equal(worldFor(1).id, "serpent");
  assert.equal(worldFor("2").id, "arcane");
  assert.equal(worldFor(3).id, "frontier");
  for (const missing of [null, undefined, "", 0, 99]) assert.equal(worldFor(missing), DEFAULT_WORLD);
  // общий атлас не изменился: лендинг и герой без класса видят прежнюю карту
  assert.equal(mapPath(5, DEFAULT_WORLD), mapPath(5));
});

test("карты миров различаются, а узлы и ориентиры остаются на холсте", () => {
  const paths = new Set(Object.values(WORLDS).map((world) => mapPath(8, world)));
  paths.add(mapPath(8));
  assert.equal(paths.size, 4);
  for (const world of Object.values(WORLDS)) {
    for (const total of [2, 8, 16]) {
      for (let i = 0; i < total; i++) {
        const { x, y } = mapCoords(i, total, world);
        assert.ok(x >= 0 && x <= 100 && y >= 10 && y <= 90, `${world.id} ${total}/${i}`);
      }
      const marks = mapLandmarks(total, world);
      assert.equal(marks.length, total - 1);
      marks.forEach((mark, i) => {
        assert.ok(world.landmarks.includes(mark.glyph));
        // ориентир не ближе 10% по высоте к обоим соседним узлам: миссию он не закрывает
        for (const node of [mapCoords(i, total, world), mapCoords(i + 1, total, world)]) {
          assert.ok(Math.abs(node.y - mark.y) >= 10, `${world.id} ${total}/${i}`);
        }
      });
    }
  }
  assert.deepEqual(mapLandmarks(8, DEFAULT_WORLD), []);
});

test("области мира делят ширину поровну", () => {
  assert.deepEqual(mapRegions(0), []);
  assert.deepEqual(mapRegions(2).map((r) => r.x), [25, 75]);
});
