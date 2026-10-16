// Код класса: ввод, ссылка и возврат к вступлению после входа. Файл читается как текст.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "join.js"), "utf8")
  .replace(/^export /gm, "");
const { normalizeJoinCode, rememberJoinCode, takeJoinCode, pathAfterAuth, joinLink } = new Function(
  `${source}; return { normalizeJoinCode, rememberJoinCode, takeJoinCode, pathAfterAuth, joinLink };`
)();

test("a code typed loosely is cleaned up", () => {
  assert.equal(normalizeJoinCode(" k7m2-qp 9x "), "K7M2QP9X");
  assert.equal(normalizeJoinCode(null), "");
  assert.equal(normalizeJoinCode(undefined), "");
});

test("without storage the code is simply not remembered", () => {
  assert.doesNotThrow(() => rememberJoinCode("K7M2QP9X"));
  assert.equal(takeJoinCode(), "");
});

test("after signing in a learner with a code goes to the join page, others where they were going", () => {
  assert.equal(pathAfterAuth("/worlds", "K7M2QP9X"), "/join/K7M2QP9X");
  assert.equal(pathAfterAuth("/worlds", ""), "/worlds");
});

test("the invitation link carries the clean code and no double slash", () => {
  assert.equal(joinLink("https://site.example/", "k7m2-qp9x"), "https://site.example/join/K7M2QP9X");
  assert.equal(joinLink("https://site.example", "AAAA2222"), "https://site.example/join/AAAA2222");
});
