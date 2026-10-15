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

/**
 * Миссии без единого открытого шага прячем: в курсе их десятки, и пустые строки закрывают сигнал.
 * @param {{steps: {opened?: number}[]}[]} missions
 * @returns {{shown: object[], hidden: object[]}}
 */
export function splitEmptyMissions(missions) {
  const shown = [];
  const hidden = [];
  (missions || []).forEach((mission) => {
    const touched = (mission.steps || []).some((step) => Number(step?.opened) > 0);
    (touched ? shown : hidden).push(mission);
  });
  return { shown, hidden };
}

/**
 * Итоги ряда «по дням» для подписи и масштаба графика.
 * @param {{active?: number, solved?: number, runs?: number}[]} daily
 */
export function dailyTotals(daily) {
  const rows = Array.isArray(daily) ? daily : [];
  const peak = rows.reduce((max, d) => Math.max(max, Number(d?.active) || 0), 0);
  const solved = rows.reduce((sum, d) => sum + (Number(d?.solved) || 0), 0);
  const runs = rows.reduce((sum, d) => sum + (Number(d?.runs) || 0), 0);
  const maxSolved = rows.reduce((max, d) => Math.max(max, Number(d?.solved) || 0), 0);
  return { days: rows.length, peak, solved, runs, maxSolved, empty: peak === 0 && solved === 0 && runs === 0 };
}
