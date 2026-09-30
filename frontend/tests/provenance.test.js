// Счётчик набора и вставки в редакторе (lib/provenance.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "provenance.js"), "utf8")
  .replace(/^export /gm, "");
const { createTracker } = new Function(`${source}; return { createTracker };`)();

function clock() {
  let t = 1000;
  return { now: () => t, tick: (ms) => (t += ms) };
}

test("typing counts characters and edits, not pastes", () => {
  const c = clock();
  const tracker = createTracker(c.now);
  tracker.record("insertText", "", "p");
  tracker.record("insertText", "p", "pr");
  c.tick(4000);
  const s = tracker.snapshot();
  assert.equal(s.typed_chars, 2);
  assert.equal(s.edit_events, 2);
  assert.equal(s.pasted_chars, 0);
  assert.equal(s.paste_count, 0);
  assert.equal(s.elapsed_ms, 4000);
});

test("a paste is counted once by its length, not again by the input event", () => {
  const tracker = createTracker(() => 0);
  tracker.paste(120);
  tracker.record("insertFromPaste", "", "x".repeat(120));
  const s = tracker.snapshot();
  assert.equal(s.pasted_chars, 120);
  assert.equal(s.paste_count, 1);
  assert.equal(s.typed_chars, 0);
  assert.equal(s.edit_events, 0);
});

test("a dropped text has no paste event: its growth is the paste", () => {
  const tracker = createTracker(() => 0);
  tracker.record("insertFromDrop", "ab", "ab" + "y".repeat(50));
  assert.equal(tracker.snapshot().pasted_chars, 50);
});

test("edits after the last paste are counted, a new paste starts the count again", () => {
  const tracker = createTracker(() => 0);
  tracker.paste(80);
  tracker.record("insertFromPaste", "", "x".repeat(80));
  tracker.record("deleteContentBackward", "x".repeat(80), "x".repeat(79));
  tracker.record("insertText", "x".repeat(79), "x".repeat(79) + "!");
  assert.equal(tracker.snapshot().edits_after_paste, 2);
  tracker.paste(10);
  tracker.record("insertFromPaste", "a", "a" + "z".repeat(10));
  assert.equal(tracker.snapshot().edits_after_paste, 0);
  assert.equal(tracker.snapshot().paste_count, 2);
});

test("reset starts a clean count (new step)", () => {
  const c = clock();
  const tracker = createTracker(c.now);
  tracker.paste(200);
  tracker.record("insertText", "", "a");
  c.tick(9000);
  tracker.reset();
  c.tick(500);
  assert.deepEqual(tracker.snapshot(), {
    pasted_chars: 0,
    typed_chars: 0,
    paste_count: 0,
    edit_events: 0,
    edits_after_paste: 0,
    elapsed_ms: 500,
  });
});

test("the snapshot carries only numbers", () => {
  const tracker = createTracker(() => 0);
  tracker.record("insertText", "", "secret");
  for (const value of Object.values(tracker.snapshot())) assert.equal(typeof value, "number");
});
