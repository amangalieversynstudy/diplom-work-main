// Форма шага Студии ↔ тело запроса (lib/studioSteps.js без сборщика): то, что уходит на сервер, когда
// преподаватель сохраняет шаг и когда шаблон курса создаёт заготовки.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "studioSteps.js"), "utf8")
  .replace(/^export /gm, "");
const { emptyStepForm, stepFromTask, stepPayload, splitHints } = new Function(
  `${source}; return { emptyStepForm, stepFromTask, stepPayload, splitHints };`
)();

const form = (patch) => ({ ...emptyStepForm(3), title_ru: " Шаг ", ...patch });

test("a story step sends its texts and no data", () => {
  const payload = stepPayload(form({ body_ru: "## Тема\nТекст", xp_reward: "5" }));
  assert.equal(payload.title_ru, "Шаг");
  assert.equal(payload.body_ru, "## Тема\nТекст");
  assert.equal(payload.xp_reward, 5);
  assert.equal(payload.order, 3);
  assert.deepEqual(payload.data, {});
  assert.ok(!("mission" in payload));
});

test("a quiz keeps its filled options and takes the key from the marked one", () => {
  const payload = stepPayload(form({ task_type: "quiz", options: [" 3 ", "", "2", "4"], correct: 0 }));
  assert.deepEqual(payload.data, {
    options: [
      { value: "3", label: "3" },
      { value: "2", label: "2" },
      { value: "4", label: "4" },
    ],
    correct_answer: "3",
  });
});

test("a quiz without a marked answer or two options is not sent", () => {
  assert.equal(stepPayload(form({ task_type: "quiz", options: ["Да", ""], correct: 1 })), null);
  assert.equal(stepPayload(form({ task_type: "quiz", options: ["Да", "  "], correct: 0 })), null);
});

test("a code step pairs its hints, keeps the check and parses the variants", () => {
  const payload = stepPayload(
    form({
      task_type: "code",
      starter: "x = {{n}}\n",
      expected_output: "{{n}}",
      hidden_check: "assert x == {{n}}",
      hints_ru: "Первая\n\nВторая",
      hints_en: "First",
      skeleton_ru: "x = ...\n",
      not_yet: ["def"],
      variants_json: '[{"vars": {"n": 1}}, {"vars": {"n": 2}}]',
    })
  );
  assert.deepEqual(payload.data, {
    starter: "x = {{n}}\n",
    expected_output: "{{n}}",
    hidden_check: "assert x == {{n}}",
    hints: [
      { ru: "Первая", en: "First" },
      { ru: "Вторая", en: "" },
    ],
    skeleton: { ru: "x = ...\n", en: "" },
    not_yet: ["def"],
    variants: [{ vars: { n: 1 } }, { vars: { n: 2 } }],
  });
});

test("variants that are not JSON keep the form from being sent", () => {
  assert.equal(stepPayload(form({ task_type: "code", expected_output: "1", variants_json: "[{vars:" })), null);
});

test("a step from the server comes back to the same request", () => {
  const task = {
    id: 7,
    task_type: "code",
    order: 2,
    title_ru: "Задача",
    title_en: "Task",
    body_ru: "Текст",
    body_en: "",
    xp_reward: 20,
    estimated_minutes: 7,
    data: {
      language: "python",
      starter: "total = 0\n",
      expected_output: "Итого: 350",
      hidden_check: "assert total == 350",
      hints: [{ ru: "Цикл", en: "Loop" }],
      skeleton: { ru: "total = ...", en: "total = ..." },
      not_yet: ["lambda"],
      variants: [],
    },
  };
  const payload = stepPayload(stepFromTask(task));
  assert.equal(payload.order, 2);
  const { language, ...sent } = task.data;
  assert.equal(language, "python");
  assert.deepEqual(payload.data, sent);

  const quiz = { id: 8, task_type: "quiz", order: 1, data: { options: [{ value: "a" }, { value: "b" }], correct_answer: "b" } };
  assert.deepEqual(stepPayload(stepFromTask(quiz)).data, {
    options: [
      { value: "a", label: "a" },
      { value: "b", label: "b" },
    ],
    correct_answer: "b",
  });
});

test("hints are split on blank lines, even with spaces in them", () => {
  assert.deepEqual(splitHints("  один \n \n два\n\n\nтри  "), ["один", "два", "три"]);
  assert.deepEqual(splitHints(""), []);
});
