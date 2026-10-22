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
    active_ms: 500,
    away_ms: 0,
    away_count: 0,
    longest_away_ms: 0,
    pause_count: 0,
    longest_pause_ms: 0,
    first_key_ms: 0,
    paste_after_away: 0,
  });
});

test("the snapshot carries only numbers", () => {
  const tracker = createTracker(() => 0);
  tracker.record("insertText", "", "secret");
  for (const value of Object.values(tracker.snapshot())) assert.equal(typeof value, "number");
});

test("active time caps each gap at the pause limit and counts pauses", () => {
  const c = clock();
  const tr = createTracker(c.now);
  c.tick(2000);
  tr.activity();
  c.tick(40000); // пауза: активно только 15 с
  tr.activity();
  c.tick(5000);
  tr.activity();
  const s = tr.snapshot();
  assert.equal(s.active_ms, 2000 + 15000 + 5000);
  assert.equal(s.pause_count, 1);
  assert.equal(s.longest_pause_ms, 40000);
  assert.equal(s.elapsed_ms, 47000);
});

test("hidden then blur is one absence", () => {
  const c = clock();
  const tr = createTracker(c.now);
  tr.activity();
  c.tick(1000);
  tr.away(); // hidden
  c.tick(2000);
  tr.away(); // blur поверх
  c.tick(3000);
  tr.back();
  const s = tr.snapshot();
  assert.equal(s.away_count, 1);
  assert.equal(s.away_ms, 5000);
  assert.equal(s.longest_away_ms, 5000);
  assert.equal(s.active_ms, 1000);
  assert.equal(s.pause_count, 0);
});

test("time away is never active and the gap across it is not a pause", () => {
  const c = clock();
  const tr = createTracker(c.now);
  tr.activity();
  tr.away();
  c.tick(60000);
  tr.activity(); // во время ухода не считается
  tr.back();
  c.tick(3000);
  tr.activity();
  const s = tr.snapshot();
  assert.equal(s.active_ms, 3000);
  assert.equal(s.pause_count, 0);
  assert.equal(s.away_ms, 60000);
});

test("paste within 30 s after a 10 s absence counts", () => {
  const c = clock();
  const tr = createTracker(c.now);
  tr.away();
  c.tick(12000);
  tr.back();
  c.tick(5000);
  tr.paste(50);
  assert.equal(tr.snapshot().paste_after_away, 1);
});

test("paste later than 30 s after returning does not count", () => {
  const c = clock();
  const tr = createTracker(c.now);
  tr.away();
  c.tick(12000);
  tr.back();
  c.tick(31000);
  tr.paste(50);
  assert.equal(tr.snapshot().paste_after_away, 0);
});

test("an absence under 10 s does not count for paste_after_away; drop counts via record", () => {
  const c = clock();
  const tr = createTracker(c.now);
  tr.away();
  c.tick(9000);
  tr.back();
  tr.paste(50);
  assert.equal(tr.snapshot().paste_after_away, 0);
  const tr2 = createTracker(c.now);
  tr2.away();
  c.tick(11000);
  tr2.back();
  c.tick(1000);
  tr2.record("insertFromDrop", "", "abcdef");
  assert.equal(tr2.snapshot().paste_after_away, 1);
});

test("first_key_ms is the time to the first non-paste edit, 0 if none", () => {
  const c = clock();
  const tr = createTracker(c.now);
  c.tick(4000);
  tr.paste(3);
  assert.equal(tr.snapshot().first_key_ms, 0);
  c.tick(2000);
  tr.record("insertText", "", "a");
  c.tick(9000);
  tr.record("insertText", "a", "ab");
  assert.equal(tr.snapshot().first_key_ms, 6000);
});

test("reset clears timing, an open absence is included in snapshot", () => {
  const c = clock();
  const tr = createTracker(c.now);
  tr.away();
  c.tick(7000);
  let s = tr.snapshot();
  assert.equal(s.away_ms, 7000);
  assert.equal(s.away_count, 1);
  assert.equal(s.longest_away_ms, 7000);
  tr.reset();
  s = tr.snapshot();
  assert.equal(s.away_ms, 0);
  assert.equal(s.away_count, 0);
  assert.equal(s.active_ms, 0);
  assert.equal(s.first_key_ms, 0);
});
