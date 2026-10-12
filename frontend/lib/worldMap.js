// Геометрия карты миров (экран /worlds и лендинг). Чистые функции без React и DOM,
// поэтому их проверяют тесты node --test.
//
// Координаты узлов даны в процентах холста: x растёт слева направо, y качается вокруг середины.

const X_VARIATIONS = [0, 4, -3, 5, -4, 2, -2, 3];
const Y_OFFSETS = [15, -25, 5, -30, 20, -10, 35, -20];
const CP1_Y = [60, -55, 65, -50, 70, -60, 55, -65];
const CP2_Y = [-60, 55, -65, 50, -70, 60, -55, 65];
const CP1_X = [0.2, 0.25, 0.2, 0.3, 0.25, 0.2, 0.3, 0.25];
const CP2_X = [0.8, 0.75, 0.8, 0.7, 0.75, 0.8, 0.7, 0.75];

// Где стоит узел index из total (в процентах холста).
export function mapCoords(index, total) {
  const step = total > 1 ? 72 / (total - 1) : 0;
  let xVar = X_VARIATIONS[index % X_VARIATIONS.length];
  if (index === 0 || index === total - 1) xVar = 0;
  return {
    x: 8 + index * step + xVar,
    y: 50 + Y_OFFSETS[index % Y_OFFSETS.length],
  };
}

// Строка d для SVG-тропы через все узлы; для пустой карты пустая строка.
export function mapPath(total) {
  if (!total || total < 1) return "";
  const first = mapCoords(0, total);
  let path = `M ${first.x} ${first.y}`;
  for (let i = 1; i < total; i++) {
    const prev = mapCoords(i - 1, total);
    const curr = mapCoords(i, total);
    const cp1X = prev.x + (curr.x - prev.x) * CP1_X[i % CP1_X.length];
    const cp1Y = prev.y + CP1_Y[i % CP1_Y.length];
    const cp2X = prev.x + (curr.x - prev.x) * CP2_X[i % CP2_X.length];
    const cp2Y = curr.y + CP2_Y[i % CP2_Y.length];
    path += ` C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${curr.x} ${curr.y}`;
  }
  return path;
}
