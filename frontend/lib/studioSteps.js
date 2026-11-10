// Форма шага Студии и тело запроса к серверу (backend/game/studio.py, StudioTaskSerializer).
// Чистые функции без импортов: их берут форма шага (components/StudioTasks.jsx), заготовки курса по шаблону
// (lib/studioTemplates.js, courseOutline) и тесты node --test, которые читают файл как текст.

export const emptyStepForm = (order) => ({
  id: null,
  task_type: "story",
  title_ru: "",
  title_en: "",
  body_ru: "",
  body_en: "",
  order,
  xp_reward: 0,
  estimated_minutes: 5,
  options: ["", ""],
  correct: 0,
  starter: "",
  expected_output: "",
  hidden_check: "",
  hints_ru: "",
  hints_en: "",
  skeleton_ru: "",
  skeleton_en: "",
  not_yet: [],
  variants_json: "",
});

// Подсказки разделяются пустой строкой; i-я русская парится с i-й английской.
export const splitHints = (text) =>
  (text || "")
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);

export const joinHints = (hints, lang) => (hints || []).map((h) => h?.[lang] || "").join("\n\n");

// Шаг с сервера → поля формы.
export const stepFromTask = (task) => {
  const options = (task.data?.options || []).map((o) => o.value);
  return {
    id: task.id,
    task_type: task.task_type,
    title_ru: task.title_ru || "",
    title_en: task.title_en || "",
    body_ru: task.body_ru || "",
    body_en: task.body_en || "",
    order: task.order,
    xp_reward: task.xp_reward ?? 0,
    estimated_minutes: task.estimated_minutes ?? 5,
    options: options.length >= 2 ? options : ["", ""],
    correct: Math.max(0, options.indexOf(task.data?.correct_answer)),
    starter: task.data?.starter || "",
    expected_output: task.data?.expected_output || "",
    hidden_check: task.data?.hidden_check || "",
    hints_ru: joinHints(task.data?.hints, "ru"),
    hints_en: joinHints(task.data?.hints, "en"),
    skeleton_ru: task.data?.skeleton?.ru || "",
    skeleton_en: task.data?.skeleton?.en || "",
    not_yet: Array.isArray(task.data?.not_yet) ? task.data.not_yet : [],
    variants_json: Array.isArray(task.data?.variants) ? JSON.stringify(task.data.variants, null, 2) : "",
  };
};

// Поля формы → тело запроса (без миссии: её добавляет вызывающий). null, если форма заполнена неверно
// (у квиза нет ответа или двух вариантов, варианты задачи — не JSON); сервер всё равно проверит ещё раз.
export const stepPayload = (form) => {
  const payload = {
    task_type: form.task_type,
    title_ru: (form.title_ru || "").trim(),
    title_en: (form.title_en || "").trim(),
    body_ru: form.body_ru || "",
    body_en: form.body_en || "",
    order: Number(form.order) || 1,
    xp_reward: Number(form.xp_reward) || 0,
    estimated_minutes: Number(form.estimated_minutes) || 5,
  };
  if (form.task_type === "quiz") {
    const answer = (form.options[form.correct] || "").trim();
    const options = form.options.map((v) => v.trim()).filter(Boolean);
    if (!answer || options.length < 2) return null;
    payload.data = {
      options: options.map((value) => ({ value, label: value })),
      correct_answer: answer,
    };
  } else if (form.task_type === "code") {
    const ru = splitHints(form.hints_ru);
    const en = splitHints(form.hints_en);
    let variants = [];
    if ((form.variants_json || "").trim()) {
      try {
        variants = JSON.parse(form.variants_json);
      } catch {
        return null; // не JSON: форма заполнена неверно
      }
    }
    payload.data = {
      starter: form.starter || "",
      expected_output: form.expected_output || "",
      hidden_check: form.hidden_check || "",
      hints: Array.from({ length: Math.max(ru.length, en.length) }, (_, i) => ({
        ru: ru[i] || "",
        en: en[i] || "",
      })),
      skeleton: { ru: form.skeleton_ru || "", en: form.skeleton_en || "" },
      not_yet: form.not_yet || [],
      variants,
    };
  } else {
    payload.data = {};
  }
  return payload;
};
