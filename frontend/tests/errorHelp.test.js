// Разбор типа ошибки Python из текста вывода (lib/errorHelp.js без сборщика).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs
  .readFileSync(path.join(__dirname, "..", "lib", "errorHelp.js"), "utf8")
  .replace(/^export /gm, "");
const { detectErrorType, ERROR_TYPES } = new Function(`${source}; return { detectErrorType, ERROR_TYPES };`)();

const tb = (last) =>
  `Traceback (most recent call last):\r\n  File "main.py", line 3, in <module>\r\n    print(x)\r\n${last}\r\n`;

test("detects each supported error type from a traceback", () => {
  const samples = {
    NameError: "NameError: name 'x' is not defined",
    TypeError: "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
    ZeroDivisionError: "ZeroDivisionError: division by zero",
    ValueError: "ValueError: invalid literal for int() with base 10: 'a'",
    IndexError: "IndexError: list index out of range",
    KeyError: "KeyError: 'name'",
    AttributeError: "AttributeError: 'int' object has no attribute 'push'",
    ImportError: "ImportError: cannot import name 'x' from 'y'",
  };
  for (const [type, line] of Object.entries(samples)) assert.equal(detectErrorType(tb(line)), type);
});

test("syntax errors have no traceback header", () => {
  const out = '  File "main.py", line 1\r\n    print("hi"\r\n         ^\r\nSyntaxError: \'(\' was never closed\r\n';
  assert.equal(detectErrorType(out), "SyntaxError");
});

test("subclasses map to their explained parent", () => {
  assert.equal(detectErrorType(tb("IndentationError: unexpected indent")), "IndentationError");
  assert.equal(detectErrorType(tb("TabError: inconsistent use of tabs")), "IndentationError");
  assert.equal(detectErrorType(tb("ModuleNotFoundError: No module named 'foo'")), "ImportError");
  assert.equal(detectErrorType(tb("UnboundLocalError: local variable 'a' referenced")), "NameError");
});

test("strips colour codes and ignores unknown or empty output", () => {
  assert.equal(detectErrorType("\u001b[31mNameError: name 'a' is not defined\u001b[0m"), "NameError");
  assert.equal(detectErrorType(tb("RuntimeError: boom")), null);
  assert.equal(detectErrorType("hello\nworld"), null);
  assert.equal(detectErrorType(""), null);
  assert.equal(detectErrorType(undefined), null);
  assert.ok(ERROR_TYPES.includes("KeyError"));
});

test("a code line mentioning an error name is not taken for the error", () => {
  const out = '  File "main.py", line 2\r\n    raise ValueError("x")\r\nTypeError: bad\r\n';
  assert.equal(detectErrorType(out), "TypeError");
});
