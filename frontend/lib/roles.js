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

/** Куда вести после входа: преподавателя в кабинет, ученика на карту. */
export function homePathFor(me) {
  return canTeach(me) ? "/teacher" : "/worlds";
}
