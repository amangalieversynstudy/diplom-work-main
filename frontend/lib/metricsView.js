// Как показать клетку карты отсева. Чистая функция, чтобы её можно было проверить без сборщика.

/**
 * Клетка шага на карте отсева.
 * - "empty": шаг никто не открыл;
 * - "few": исход известен меньше чем у minSample пар, процент по таким данным ничего не говорит
 *   (один ушедший из одного не должен краситься в ярко-красные 100%), клетка серая;
 * - "ok": процент и цвет по доле ушедших.
 * @returns {{state: "empty" | "few" | "ok", text: string, rate: number | null}}
 */
export function heatCellState(step, minSample) {
  const opened = Number(step?.opened) || 0;
  const known = Number(step?.known) || 0;
  if (!opened) return { state: "empty", text: "·", rate: null };
  if (known < minSample || step?.dropout_rate == null) {
    return { state: "few", text: `n=${known}`, rate: null };
  }
  return { state: "ok", text: `${Math.round(step.dropout_rate)}%`, rate: step.dropout_rate };
}

/**
 * Плитка KPI: процент по меньше чем minSample известных исходов ничего не говорит
 * («Отсев 100%» на одном шаге), вместо числа показываем «мало данных».
 * @returns {{few: boolean, n: number}}
 */
export function kpiState(n, minSample) {
  const known = Number(n) || 0;
  return { few: known < minSample, n: known };
}
