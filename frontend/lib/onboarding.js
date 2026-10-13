// Мягкий онбординг: после первой регистрации ведём ученика на выбор класса («пролог»).
// Признак — одноразовый флаг, который ставит регистрация; он снимается при первом решении,
// поэтому перенаправление не зацикливается, а старых пользователей оно не касается.

const KEY = "onboarding_pending";

export function markOnboardingPending() {
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    /* без памяти онбординг просто не покажется */
  }
}

export function isOnboardingPending() {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function clearOnboardingPending() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ничего */
  }
}

// Ответ профиля -> { isStaff, hasClass }.
export function readProfileFlags(me) {
  const isStaff = Boolean(me?.is_staff ?? me?.user?.is_staff);
  const classRole = me?.profile?.class_role ?? me?.class_role ?? me?.class_role_id ?? null;
  return { isStaff, hasClass: classRole !== null && classRole !== undefined && classRole !== "" };
}

// Нужно ли вести на выбор класса: флаг стоит, это не преподаватель и класса ещё нет.
export function shouldRedirectToClass({ pending, isStaff, hasClass }) {
  return Boolean(pending) && !isStaff && !hasClass;
}

// Куда вести после выбора класса: первый выбор (после регистрации) ведёт на карту к первой миссии,
// смена класса позже возвращает на лист героя.
export function pathAfterClassChoice(hadClass) {
  return hadClass ? "/profile" : "/worlds";
}
