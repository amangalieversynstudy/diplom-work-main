// Роль преподавателя: кабинет открывают по is_teacher, can_teach или staff. Файл читается как текст.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "roles.js"), "utf8")
  .replace(/^export /gm, "");
const { canTeach, homePathFor, isPilotTeacher } = new Function(
  `${source}; return { canTeach, homePathFor, isPilotTeacher };`
)();

test("a student cannot teach", () => {
  assert.equal(canTeach({ is_staff: false, is_teacher: false, can_teach: false }), false);
  assert.equal(canTeach(null), false);
  assert.equal(canTeach({}), false);
});

test("teacher role, staff and the combined flag all open the cabinet, flat or nested", () => {
  assert.equal(canTeach({ is_teacher: true }), true);
  assert.equal(canTeach({ is_staff: true }), true);
  assert.equal(canTeach({ can_teach: true, is_staff: false }), true);
  assert.equal(canTeach({ user: { is_teacher: true } }), true);
});

test("a false can_teach does not hide staff rights", () => {
  assert.equal(canTeach({ can_teach: false, is_staff: true }), true);
});

test("after sign-in a teacher goes to the cabinet and a student to the map", () => {
  assert.equal(homePathFor({ is_teacher: true }), "/teacher");
  assert.equal(homePathFor({ is_staff: false }), "/worlds");
});

test("only a staff teacher who did not sign up on their own answers the pilot questionnaire", () => {
  assert.equal(isPilotTeacher({ is_staff: true, is_teacher: false }), true);
  assert.equal(isPilotTeacher({ is_staff: false, is_teacher: true }), false);
  assert.equal(isPilotTeacher({ is_staff: true, is_teacher: true }), false);
  assert.equal(isPilotTeacher({ user: { is_staff: true } }), true);
  assert.equal(isPilotTeacher(null), false);
});
