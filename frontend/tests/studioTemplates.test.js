// Шаблоны Студии: каждый пресет заполняет форму целиком и проходит проверку сервера. Запуск эталонных
// решений на Python — в проверке перед коммитом; здесь — структура, которую ловит сервер. Файл читается как текст.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

// studioTemplates.js берёт разбор формы шага из studioSteps.js: склеиваем оба файла без import/export
const read = (name) =>
  fs
    .readFileSync(path.join(__dirname, "..", "lib", name), "utf8")
    .replace(/^import .*$/gm, "")
    .replace(/^export /gm, "");
const source = [read("studioSteps.js"), read("studioTemplates.js")].join("\n");
const lib = new Function(
  `${source}; return { localized, COURSE_TEMPLATES, SECTION_TEMPLATES, MISSION_TEMPLATES, STEP_TEMPLATES, ` +
    "outlineCounts, courseOutline };"
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

// Пределы сервера по умолчанию (backend/core/settings/base.py, STUDIO_LIMITS) и правила StudioTaskSerializer.
const LIMITS = { sections: 20, missions: 60, steps: 20 };

test("a course template builds 4 chapters of 2 missions with theory, a quiz and a code task in each", () => {
  const basics = lib.COURSE_TEMPLATES.find((t) => t.id === "basics");
  assert.deepEqual(lib.outlineCounts(basics), { sections: 4, missions: 8, steps: 24 });
  const outline = lib.courseOutline(basics, basics.form);
  assert.equal(outline.sections.length, 4);
  for (const section of outline.sections) {
    assert.equal(section.missions.length, 2, section.title_ru);
    for (const mission of section.missions) {
      assert.deepEqual(
        mission.steps.map((s) => s.task_type),
        ["story", "quiz", "code"],
        mission.title_ru
      );
    }
  }
});

test("every course template has an outline the server accepts", () => {
  for (const template of lib.COURSE_TEMPLATES) {
    const outline = lib.courseOutline(template, template.form);
    const counts = lib.outlineCounts(template);
    const missions = outline.sections.flatMap((s) => s.missions);
    const steps = missions.flatMap((m) => m.steps);
    assert.deepEqual(counts, { sections: outline.sections.length, missions: missions.length, steps: steps.length });
    assert.ok(counts.sections >= 1 && counts.sections <= LIMITS.sections, template.id);
    assert.ok(counts.missions >= 1 && counts.missions <= LIMITS.missions, template.id);
    for (const section of outline.sections) {
      assert.ok(section.title_ru && section.title_en, `${template.id}: section titles`);
      assert.ok(!("missions" in section.missions[0]), `${template.id}: no nesting leaks`);
    }
    for (const mission of missions) {
      const where = `${template.id}/${mission.title_ru}`;
      assert.ok(mission.title_ru && mission.title_en, where);
      assert.ok(mission.xp_reward > 0 && mission.xp_reward <= 500, where);
      assert.ok(mission.steps.length >= 2 && mission.steps.length <= LIMITS.steps, where);
      assert.ok(mission.steps.some((s) => s.task_type === "code"), `${where}: learners write code`);
      assert.deepEqual(
        mission.steps.map((s) => s.order),
        mission.steps.map((_, i) => i + 1),
        where
      );
    }
    for (const step of steps) {
      assert.ok(step, `${template.id}: every preset turns into a payload`);
      assert.ok(step.title_ru && step.title_en, template.id);
      if (step.task_type === "quiz") {
        assert.ok(step.data.options.some((o) => o.value === step.data.correct_answer), template.id);
      }
      if (step.task_type === "code") {
        // the Studio refuses a code step that would accept any code
        assert.ok(step.data.hidden_check.trim() || step.data.expected_output.trim(), template.id);
      }
    }
  }
});

test("the hint of a course template says what the outline creates", () => {
  for (const template of lib.COURSE_TEMPLATES) {
    const { missions } = lib.outlineCounts(template);
    const sections = template.outline.sections.length;
    for (const language of ["ru", "en"]) {
      const hint = template.hint[language];
      // the number of chapters (or of revision missions) is in the hint, as the outline has it
      const named = [sections, missions, template.outline.sections[0].missions.length].map(String);
      assert.ok(named.some((n) => hint.includes(n)), `${template.id}.${language}: ${hint}`);
    }
  }
});

test("the course fields come from the form the teacher edited, trimmed", () => {
  const template = lib.COURSE_TEMPLATES[0];
  const outline = lib.courseOutline(template, { title_ru: "  Мой курс ", title_en: "", description_ru: " Для 1 курса\n" });
  assert.equal(outline.title_ru, "Мой курс");
  assert.equal(outline.title_en, "");
  assert.equal(outline.description_ru, "Для 1 курса");
  assert.equal(outline.sections.length, template.outline.sections.length);
});
