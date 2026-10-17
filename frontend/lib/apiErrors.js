// Текст ошибки сервера для человека. Ответ бывает объектом DRF ({detail}, {поле: [...]}) или строкой
// (HTML-страница 502/500 от прокси). Строку показывать нельзя: раньше она выводилась по буквам.
// Файл без импортов: его читает тест как текст.

const MAX_LEN = 300;

const isText = (value) => typeof value === "string" && value.trim() !== "" && value.length <= MAX_LEN && !/^\s*</.test(value);

/** Тело ответа как объект DRF, иначе null. */
export function errorBody(error) {
  const data = error?.response?.data;
  return data && typeof data === "object" && !Array.isArray(data) ? data : null;
}

/**
 * Сообщение для тоста: detail, иначе тексты полей, иначе запасной текст.
 * Без ответа сервера (сеть, CORS) возвращает offline, если он передан.
 */
export function serverMessage(error, fallback, offline) {
  if (error && !error.response && offline) return offline;
  const data = error?.response?.data;
  if (Array.isArray(data)) {
    const texts = data.filter(isText);
    return texts.length ? texts.join(" ") : fallback;
  }
  const body = errorBody(error);
  if (!body) return fallback;
  if (isText(body.detail)) return body.detail;
  const texts = Object.values(body)
    .flat()
    .filter(isText);
  return texts.length ? texts.join(" ") : fallback;
}

/** Ошибки по полям формы: {поле: первая строка}. Только для объектного ответа. */
export function fieldErrorsFrom(error, keys) {
  const body = errorBody(error);
  const result = {};
  if (!body) return result;
  keys.forEach((key) => {
    const value = Array.isArray(body[key]) ? body[key][0] : body[key];
    if (isText(value)) result[key] = value;
  });
  return result;
}
