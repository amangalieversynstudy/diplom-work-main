// «Глазами студента»: преподаватель смотрит на платформу так, как её видит ученик. Выбор хранится в этом
// браузере; пока он включён, каждый запрос к API несёт заголовок X-View-As: student, и сервер прячет
// черновики собственных курсов преподавателя (backend/core/authentication.py). Награды не начисляются в любом
// режиме: преподаватель всегда в режиме просмотра.
const KEY = "view_as_student";
export const VIEW_MODE_EVENT = "viewmodechange";
export const VIEW_AS_HEADER = "X-View-As";

export function isStudentView() {
  try {
    return typeof window !== "undefined" && window.localStorage.getItem(KEY) === "1";
  } catch {
    return false; // приватный режим или заблокированное хранилище: обычный режим
  }
}

export function setStudentView(on) {
  try {
    if (on) window.localStorage.setItem(KEY, "1");
    else window.localStorage.removeItem(KEY);
  } catch {
    // хранилище недоступно: переключатель просто не запомнится
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(VIEW_MODE_EVENT));
}
