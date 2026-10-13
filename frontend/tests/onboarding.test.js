// Условие перенаправления на выбор класса после регистрации (lib/onboarding.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "onboarding.js"), "utf8")
  .replace(/^export /gm, "");
const { shouldRedirectToClass, readProfileFlags } = new Function(
  `${source}; return { shouldRedirectToClass, readProfileFlags };`
)();

test("redirects a fresh student without a class", () => {
  assert.equal(shouldRedirectToClass({ pending: true, isStaff: false, hasClass: false }), true);
});

test("does not redirect without the registration flag (no loop, old users untouched)", () => {
  assert.equal(shouldRedirectToClass({ pending: false, isStaff: false, hasClass: false }), false);
});

test("does not redirect teachers or users who already have a class", () => {
  assert.equal(shouldRedirectToClass({ pending: true, isStaff: true, hasClass: false }), false);
  assert.equal(shouldRedirectToClass({ pending: true, isStaff: false, hasClass: true }), false);
});

test("readProfileFlags handles nested and flat profile shapes", () => {
  assert.deepEqual(readProfileFlags({ profile: { class_role: 1 }, is_staff: false }), { isStaff: false, hasClass: true });
  assert.deepEqual(readProfileFlags({ class_role: null, user: { is_staff: true } }), { isStaff: true, hasClass: false });
  assert.deepEqual(readProfileFlags(null), { isStaff: false, hasClass: false });
});

const { pathAfterClassChoice } = new Function(`${source}; return { pathAfterClassChoice };`)();

test("first class choice leads to the map, a later change back to the profile", () => {
  assert.equal(pathAfterClassChoice(false), "/worlds");
  assert.equal(pathAfterClassChoice(true), "/profile");
});
