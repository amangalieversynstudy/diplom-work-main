// Кто может пользоваться кабинетом преподавателя, аналитикой и студией: аккаунт с ролью преподавателя
// (выбирается при регистрации) или staff. Ответ профиля бывает плоским или вложенным в user.

/** Есть ли у аккаунта доступ к кабинету, аналитике и студии. */
export function canTeach(me) {
  const flat = me || {};
  const nested = me?.user || {};
  return Boolean(
    flat.can_teach || flat.is_teacher || flat.is_staff || nested.can_teach || nested.is_teacher || nested.is_staff
  );
}

/**
 * Преподаватель пилота: staff по коду приглашения или от администратора, не самостоятельная регистрация.
 * Только ему показывается анкета удобства (SUS): ответы остальных в отчёт пилота не идут.
 */
export function isPilotTeacher(me) {
  const flat = me || {};
  const nested = me?.user || {};
  const staff = Boolean(flat.is_staff || nested.is_staff);
  const selfService = Boolean(flat.is_teacher || nested.is_teacher);
  return staff && !selfService;
}

/** Куда вести после входа: преподавателя в кабинет, ученика на карту. */
export function homePathFor(me) {
  return canTeach(me) ? "/teacher" : "/worlds";
}
