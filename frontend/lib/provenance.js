// Как код попал в редактор: сколько символов набрано и сколько вставлено.
// Считаем только числа. Ни нажатия клавиш, ни вставленный текст не сохраняются и не уходят
// на сервер (см. backend/game/authorship.py: это подсказка преподавателю, а не доказательство).

export const PAUSE_MS = 15000; // пауза между действиями: дольше этого время не считается активным
const AWAY_PASTE_MIN_MS = 10000; // отсутствие, после которого вставка считается подозрительной
const AWAY_PASTE_WINDOW_MS = 30000; // сколько после возвращения вставка ещё считается «сразу»

const PASTE_TYPES = ["insertFromPaste", "insertFromDrop", "insertFromYank"];

export function createTracker(now = () => Date.now()) {
  let state;
  let pasteSeen = false; // событие paste уже сообщило длину вставки
  let t; // время: активность, паузы, уходы со вкладки (только числа)

  const reset = () => {
    state = {
      pasted_chars: 0,
      typed_chars: 0,
      paste_count: 0,
      edit_events: 0,
      edits_after_paste: 0,
      openedAt: now(),
    };
    pasteSeen = false;
    t = {
      lastAct: state.openedAt, // последнее действие или возвращение
      active: 0,
      pauses: 0,
      longestPause: 0,
      awaySince: null, // null: ученик на странице
      awayMs: 0,
      awayCount: 0,
      longestAway: 0,
      lastAwayMs: 0,
      returnedAt: null,
      firstKey: 0,
      pasteAfterAway: 0,
    };
  };
  reset();

  const activity = () => {
    if (t.awaySince !== null) return; // пока ушёл, действий не засчитываем
    const at = now();
    const gap = Math.max(0, at - t.lastAct);
    t.active += Math.min(gap, PAUSE_MS);
    if (gap >= PAUSE_MS) {
      t.pauses += 1;
      t.longestPause = Math.max(t.longestPause, gap);
    }
    t.lastAct = at;
  };

  const countPasteAfterAway = () => {
    if (t.awaySince !== null || t.returnedAt === null) return;
    if (t.lastAwayMs >= AWAY_PASTE_MIN_MS && now() - t.returnedAt <= AWAY_PASTE_WINDOW_MS) {
      t.pasteAfterAway += 1;
    }
  };

  return {
    reset,
    /** Любое действие ученика: клавиша, нажатие, прокрутка, ввод. */
    activity,
    /** Вкладка скрыта или окно потеряло фокус. Повторный вызов ничего не меняет (уходы не двоятся). */
    away() {
      if (t.awaySince !== null) return;
      const at = now();
      t.active += Math.min(Math.max(0, at - t.lastAct), PAUSE_MS);
      t.awaySince = at;
      t.awayCount += 1;
    },
    /** Вкладка снова видна и окно в фокусе. */
    back() {
      if (t.awaySince === null) return;
      const at = now();
      const dur = Math.max(0, at - t.awaySince);
      t.awayMs += dur;
      t.longestAway = Math.max(t.longestAway, dur);
      t.lastAwayMs = dur;
      t.returnedAt = at;
      t.lastAct = at;
      t.awaySince = null;
    },
    /** Длина вставленного текста (событие paste у textarea). */
    paste(length) {
      countPasteAfterAway();
      activity();
      state.pasted_chars += Math.max(0, Number(length) || 0);
      state.paste_count += 1;
      state.edits_after_paste = 0;
      pasteSeen = true;
    },
    /** Каждое изменение текста в редакторе: тип ввода, текст до и после. */
    record(inputType, previous, next) {
      const delta = (next || "").length - (previous || "").length;
      if (PASTE_TYPES.includes(inputType)) {
        if (!pasteSeen) {
          countPasteAfterAway();
          activity();
          // перетаскивание текста не даёт события paste: берём прирост длины
          state.pasted_chars += Math.max(0, delta);
          state.paste_count += 1;
          state.edits_after_paste = 0;
        }
        pasteSeen = false;
        return;
      }
      activity();
      if (!t.firstKey) t.firstKey = Math.max(1, now() - state.openedAt);
      state.edit_events += 1;
      if (state.paste_count > 0) state.edits_after_paste += 1;
      if (delta > 0) state.typed_chars += delta;
    },
    /** Числа для сервера. */
    snapshot() {
      const { openedAt, ...counts } = state;
      const at = now();
      const away = t.awaySince !== null;
      const openAway = away ? Math.max(0, at - t.awaySince) : 0;
      const trailing = away ? 0 : Math.min(Math.max(0, at - t.lastAct), PAUSE_MS);
      return {
        ...counts,
        elapsed_ms: Math.max(0, at - openedAt),
        active_ms: Math.round(t.active + trailing),
        away_ms: Math.round(t.awayMs + openAway),
        away_count: t.awayCount,
        longest_away_ms: Math.round(Math.max(t.longestAway, openAway)),
        pause_count: t.pauses,
        longest_pause_ms: Math.round(t.longestPause),
        first_key_ms: Math.round(t.firstKey),
        paste_after_away: t.pasteAfterAway,
      };
    },
  };
}
