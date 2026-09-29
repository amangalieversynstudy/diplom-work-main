// Числительные: «1 ученик», «2 ученика», «5 учеников». В английском только два вида.
// Слова лежат в словаре: units.<имя>_one / _few / _many.

export function pluralCategory(n, language = "ru") {
  const abs = Math.abs(Math.trunc(Number(n) || 0));
  if (language === "en") return abs === 1 ? "one" : "many";
  const mod10 = abs % 10;
  const mod100 = abs % 100;
  if (mod10 === 1 && mod100 !== 11) return "one";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "few";
  return "many";
}

/** Слово в нужной форме: unit(t, language, "student", 5) → «учеников». */
export function unit(t, language, name, n) {
  return t(`units.${name}_${pluralCategory(n, language)}`);
}
