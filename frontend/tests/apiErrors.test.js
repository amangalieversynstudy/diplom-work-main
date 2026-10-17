// Ошибки сервера: HTML-страница прокси не должна попадать в тост по буквам. Файл читается как текст.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "apiErrors.js"), "utf8")
  .replace(/^export /gm, "");
const { serverMessage, fieldErrorsFrom, errorBody } = new Function(
  `${source}; return { serverMessage, fieldErrorsFrom, errorBody };`
)();

const html = { response: { status: 502, data: "<!DOCTYPE html><html lang=\"ru\"><head><title>RPG</title></head></html>" } };

test("an HTML error page becomes the fallback text, not a list of letters", () => {
  assert.equal(serverMessage(html, "Сервер недоступен"), "Сервер недоступен");
  assert.deepEqual(fieldErrorsFrom(html, ["username"]), {});
  assert.equal(errorBody(html), null);
});

test("DRF detail wins, then field messages", () => {
  assert.equal(serverMessage({ response: { data: { detail: "Нет доступа" } } }, "x"), "Нет доступа");
  assert.equal(
    serverMessage({ response: { data: { username: ["Занято."], password: ["Коротко."] } } }, "x"),
    "Занято. Коротко."
  );
});

test("field errors take the first message of each requested field", () => {
  const err = { response: { data: { username: ["Занято.", "ещё"], role: "Закрыто.", other: ["x"] } } };
  assert.deepEqual(fieldErrorsFrom(err, ["username", "role", "email"]), { username: "Занято.", role: "Закрыто." });
});

test("no response at all means the network, with its own message", () => {
  assert.equal(serverMessage(new Error("Network Error"), "fallback", "Нет связи"), "Нет связи");
  assert.equal(serverMessage(new Error("Network Error"), "fallback"), "fallback");
});

test("a list body and oversized strings are handled", () => {
  assert.equal(serverMessage({ response: { data: ["Ошибка A"] } }, "x"), "Ошибка A");
  assert.equal(serverMessage({ response: { data: { detail: "a".repeat(400) } } }, "x"), "x");
});
