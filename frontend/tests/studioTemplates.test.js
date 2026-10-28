// Шаблоны Студии: каждый пресет заполняет форму целиком и проходит проверку сервера. Запуск эталонных
// решений на Python — в проверке перед коммитом; здесь — структура, которую ловит сервер. Файл читается как текст.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "studioTemplates.js"), "utf8")
  .replace(/^export /gm, "");
const lib = new Function(
  `${source}; return { localized, COURSE_TEMPLATES, SECTION_TEMPLATES, MISSION_TEMPLATES, STEP_TEMPLATES };`
)();

const ALL = ["COURSE_TEMPLATES", "SECTION_TEMPLATES", "MISSION_TEMPLATES", "STEP_TEMPLATES"];
const PLACEHOLDER = /\{\{\s*(\w+)\s*\}\}/g;
const CONSTRUCTS = ["def", "lambda", "comprehension", "try", "import", "class", "with"];

test("every group has 3-4 presets with unique ids and labels in both languages", () => {
  for (const name of ALL) {
    const group = lib[name];
    assert.ok(group.length >= 3 && group.length <= 4, name);
    assert.equal(new Set(group.map((t) => t.id)).size, group.length, name);
    for (const template of group) {
      for (const field of ["label", "hint"]) {
        assert.ok(template[field].ru && template[field].en, `${name}/${template.id}.${field}`);
      }
      assert.ok(template.form.title_ru && template.form.title_en, `${name}/${template.id}: titles`);
    }
  }
});

test("localized picks the language and falls back to Russian", () => {
  assert.equal(lib.localized({ ru: "Да", en: "Yes" }, "en"), "Yes");
  assert.equal(lib.localized({ ru: "Да" }, "en"), "Да");
  assert.equal(lib.localized("просто", "en"), "просто");
  assert.equal(lib.localized(null, "ru"), "");
});

test("mission rewards stay inside the server's 0-500 XP", () => {
  for (const template of lib.MISSION_TEMPLATES) {
    assert.ok(template.form.xp_reward > 0 && template.form.xp_reward <= 500, template.id);
  }
});

test("the step presets cover the three step types and stay inside the server's limits", () => {
  const types = new Set(lib.STEP_TEMPLATES.map((t) => t.form.task_type));
  assert.deepEqual([...types].sort(), ["code", "quiz", "story"]);
  for (const { id, form } of lib.STEP_TEMPLATES) {
    assert.ok(form.xp_reward >= 0 && form.xp_reward <= 100, id);
    assert.ok(form.estimated_minutes >= 1 && form.estimated_minutes <= 240, id);
  }
});

test("the quiz key is one of its distinct options", () => {
  for (const { id, form } of lib.STEP_TEMPLATES.filter((t) => t.form.task_type === "quiz")) {
    assert.ok(form.options.length >= 2 && form.options.length <= 8, id);
    assert.equal(new Set(form.options.map((o) => o.toLowerCase())).size, form.options.length, id);
    assert.ok(form.options[form.correct], id);
  }
});

test("code presets: reference solution, known constructs, consistent variants", () => {
  for (const { id, form, reference } of lib.STEP_TEMPLATES.filter((t) => t.form.task_type === "code")) {
    assert.ok(form.expected_output && reference, id);
    assert.ok(form.not_yet.every((name) => CONSTRUCTS.includes(name)), id);
    // the hidden check must not be the expected output itself
    assert.ok(!form.hidden_check.includes(form.expected_output), id);
    if (!form.variants_json) continue;
    const variants = JSON.parse(form.variants_json);
    assert.ok(variants.length >= 2 && variants.length <= 30, id);
    const keys = JSON.stringify(Object.keys(variants[0].vars).sort());
    for (const variant of variants) assert.equal(JSON.stringify(Object.keys(variant.vars).sort()), keys, id);
    const used = new Set();
    for (const text of [form.body_ru, form.starter, form.expected_output, form.hidden_check, reference]) {
      for (const match of text.matchAll(PLACEHOLDER)) used.add(match[1]);
    }
    for (const name of used) assert.ok(name in variants[0].vars, `${id}: {{${name}}} has no value`);
  }
});

test("a code preset never shows its own answer in the task text", () => {
  for (const { id, form } of lib.STEP_TEMPLATES.filter((t) => t.form.task_type === "code")) {
    if (form.variants_json) {
      for (const { vars } of JSON.parse(form.variants_json)) {
        const answer = form.expected_output.replace(PLACEHOLDER, (_, key) => String(vars[key]));
        const body = form.body_ru.replace(PLACEHOLDER, (_, key) => String(vars[key]));
        assert.ok(!body.includes(answer), `${id}: ${answer}`);
      }
    } else {
      assert.ok(!form.body_ru.includes(form.expected_output), id);
    }
  }
});
