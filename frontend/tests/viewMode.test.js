// «Глазами студента»: выбор хранится в браузере и не ломает страницу без хранилища. Файл читается как текст.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "viewMode.js"), "utf8")
  .replace(/^export /gm, "");

function load(window) {
  return new Function("window", `${source}; return { isStudentView, setStudentView, VIEW_MODE_EVENT, VIEW_AS_HEADER };`)(
    window
  );
}

function fakeWindow({ broken = false } = {}) {
  const store = new Map();
  const events = [];
  const storage = {
    getItem: (k) => {
      if (broken) throw new Error("blocked");
      return store.has(k) ? store.get(k) : null;
    },
    setItem: (k, v) => {
      if (broken) throw new Error("blocked");
      store.set(k, String(v));
    },
    removeItem: (k) => store.delete(k),
  };
  return { localStorage: storage, dispatchEvent: (e) => events.push(e.type), events };
}

test("off by default, on after the switch, off again, and every change is announced", () => {
  const win = fakeWindow();
  const mode = load(win);
  assert.equal(mode.isStudentView(), false);
  mode.setStudentView(true);
  assert.equal(mode.isStudentView(), true);
  mode.setStudentView(false);
  assert.equal(mode.isStudentView(), false);
  assert.deepEqual(win.events, [mode.VIEW_MODE_EVENT, mode.VIEW_MODE_EVENT]);
});

test("a blocked storage means the normal mode, not a crash", () => {
  const mode = load(fakeWindow({ broken: true }));
  assert.equal(mode.isStudentView(), false);
  assert.doesNotThrow(() => mode.setStudentView(true));
});

test("the header name matches the backend (core/authentication.py)", () => {
  assert.equal(load(fakeWindow()).VIEW_AS_HEADER, "X-View-As");
});
