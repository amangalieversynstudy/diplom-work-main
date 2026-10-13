// Двойной щелчок по «Запустить»: второй клик попадает на уже показанную кнопку «Остановить».
// Остановкой считаем только щелчок, сделанный позже этого порога после старта.
export const STOP_GUARD_MS = 700;

export function isAccidentalStop(startedAt, now) {
  return now - startedAt < STOP_GUARD_MS;
}
