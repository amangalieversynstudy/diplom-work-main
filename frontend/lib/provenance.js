// Как код попал в редактор: сколько символов набрано и сколько вставлено.
// Считаем только числа. Ни нажатия клавиш, ни вставленный текст не сохраняются и не уходят
// на сервер (см. backend/game/authorship.py: это подсказка преподавателю, а не доказательство).

const PASTE_TYPES = ["insertFromPaste", "insertFromDrop", "insertFromYank"];

export function createTracker(now = () => Date.now()) {
  let state;
  let pasteSeen = false; // событие paste уже сообщило длину вставки

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
  };
  reset();

  return {
    reset,
    /** Длина вставленного текста (событие paste у textarea). */
    paste(length) {
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
          // перетаскивание текста не даёт события paste: берём прирост длины
          state.pasted_chars += Math.max(0, delta);
          state.paste_count += 1;
          state.edits_after_paste = 0;
        }
        pasteSeen = false;
        return;
      }
      state.edit_events += 1;
      if (state.paste_count > 0) state.edits_after_paste += 1;
      if (delta > 0) state.typed_chars += delta;
    },
    /** Числа для сервера. */
    snapshot() {
      const { openedAt, ...counts } = state;
      return { ...counts, elapsed_ms: Math.max(0, now() - openedAt) };
    },
  };
}
