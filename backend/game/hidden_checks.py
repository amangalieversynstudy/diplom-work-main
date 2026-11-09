"""Hidden checks of code steps, graded so that the learner's own code cannot fake a pass.

A course author writes a hidden check as plain Python that runs after the learner's solution and calls
it with other values, for example ``assert power(3, 4) == 81``. The sandbox runs the learner's code, and
whatever the sandbox holds, that code can read or change. So the expected values never go there:

* a top-level ``assert <expr> <op> <value>``, where ``<value>`` is a plain value (a literal, or constant
  arithmetic such as ``7 * (7 + 1) // 2``), becomes a *value probe*: the sandbox only reports the value
  of ``<expr>``; the operator and ``<value>`` stay on the server, which compares them itself;
* any other top-level ``assert <test>`` becomes a *truth probe* that reports whether the test holds;
* ``assert a and b`` gives one probe per part;
* the rest of the check (assignments, classes, ``try`` blocks, asserts inside loops) runs as written.

``program`` builds what the sandbox runs: the learner's code in a fresh ``__main__`` module, then the
rewritten check in the same namespace. It prints none of the learner's output, only one report line per
probe and a last line once the check has run to its end. ``passed`` accepts a run only if it ended
normally, that last line is there, every probe reported, and every reported value satisfies its
comparison on the server. A report that cannot be read, or that no probe asked for, fails the run.

A report can only say what the program computed, and a value probe passes only with the value a right
solution computes: that value is nowhere in the sandbox. A check made only of truth probes is weaker
(``Plan.weak``); ``pilot_check`` lists such steps and Studio suggests comparing calls with values.
"""

import ast
import binascii
import dis
import json
import operator
from dataclasses import dataclass

MARK = "<<hidden-check>> "  # starts every report line of the sandbox program
PROBE = "__hidden_check_probe__"  # what the rewritten check calls in the learner's namespace

VALUE, TRUTH = "v", "t"

# The comparisons the server does itself, on plain values only.
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}
# ``x is 5`` depends on the interpreter; ``is`` is compared on the server only against these
_SINGLETONS = (None, True, False, Ellipsis)

# bytecode of an expression the compiler folded into one constant (names differ between Python versions)
_FOLDED_LOADS = frozenset({"LOAD_CONST", "RETURN_CONST", "LOAD_SMALL_INT"})
_FOLDED_NOISE = frozenset({"RESUME", "NOP", "CACHE", "EXTENDED_ARG", "RETURN_VALUE"})


@dataclass(frozen=True, eq=False)
class Probe:
    """One top-level comparison of the check: what the sandbox reports and how the server judges it."""

    kind: str  # VALUE or TRUTH
    op: type = None  # the ast comparison class of a value probe
    expected: object = None  # the plain value it is compared with; never sent to the sandbox
    reported_left: bool = True  # the reported value is the left operand of the comparison

    def accepts(self, value):
        if self.kind == TRUTH:
            return value is True
        left, right = (value, self.expected) if self.reported_left else (self.expected, value)
        try:
            return bool(_COMPARE[self.op](left, right))
        except Exception:  # e.g. ordering a str against an int: the assert would have raised too
            return False


@dataclass(frozen=True)
class Plan:
    """A hidden check prepared for a run: the source the sandbox gets and the probes the server judges."""

    source: str  # the check, with each top-level assert replaced by probe calls
    probes: tuple

    @property
    def weak(self):
        """No value probe: every probe is a yes/no that the sandbox reports."""
        return not any(probe.kind == VALUE for probe in self.probes)


def compile_check(check):
    """The plan of *check*, the Python source of a hidden check. Raises SyntaxError if it does not parse."""
    text = check.replace("\r\n", "\n").replace("\r", "\n")
    tree = ast.parse(text)
    starts = [0] + [i + 1 for i, char in enumerate(text) if char == "\n"]
    probes, edits = [], []
    for node in tree.body:
        if not isinstance(node, ast.Assert):
            continue
        calls = []
        for part in _parts(node.test):
            probe, reported = _probe(part)
            calls.append(f"{PROBE}({len(probes)}, ({ast.get_source_segment(text, reported)}))")
            probes.append(probe)
        start = _offset(text, starts, node.lineno, node.col_offset)
        end = _offset(text, starts, node.end_lineno, node.end_col_offset)
        edits.append((start, end, "; ".join(calls)))
    for start, end, calls in reversed(edits):
        text = text[:start] + calls + text[end:]
    return Plan(text, tuple(probes))


def _offset(text, starts, lineno, col):
    """Index in *text* of an ast position (line from 1, column in UTF-8 bytes)."""
    line_start = starts[lineno - 1]
    line_end = starts[lineno] if lineno < len(starts) else len(text)
    line = text[line_start:line_end]
    return line_start + len(line.encode("utf-8")[:col].decode("utf-8"))


def _parts(test):
    """``a and b and c`` -> [a, b, c]: each part is judged on its own."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return [part for value in test.values for part in _parts(value)]
    return [test]


def _probe(test):
    """The probe for one assert test, and the expression whose value the sandbox reports."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op = type(test.ops[0])
        left, right = test.left, test.comparators[0]
        for reported_left, reported, other in ((True, left, right), (False, right, left)):
            plain, value = _plain(other)
            if plain and not _plain(reported)[0] and _comparable(op, value):
                return Probe(VALUE, op, value, reported_left), reported
    return Probe(TRUTH), test


def _comparable(op, value):
    return op not in (ast.Is, ast.IsNot) or any(value is single for single in _SINGLETONS)


def _plain(node):
    """``(True, value)`` if *node* is a value the server can know without running anything."""
    try:
        return True, ast.literal_eval(node)
    except Exception:
        pass
    # Constant arithmetic (``7 * (7 + 1) // 2``, ``"-" * 10``): the compiler folds it into one constant
    # within its own size limits, so nothing of the check is run here.
    try:
        code = compile(ast.Expression(body=node), "<hidden check>", "eval")
    except Exception:
        return False, None
    constants = []
    for instruction in dis.get_instructions(code):
        if instruction.opname in _FOLDED_LOADS:
            constants.append(instruction.argval)
        elif instruction.opname not in _FOLDED_NOISE:
            return False, None
    if code.co_names or len(constants) != 1:
        return False, None
    return True, constants[0]


# ── the program for the sandbox ─────────────────────────────────────────────
# It must run on the sandbox's Python (Judge0 CE: 3.8), so it sticks to old syntax and APIs.

_HEAD = """\
# RPG Academy: a hidden check of a code step. The expected values are not in this program:
# it reports what the check's calls return, and the server compares.
import binascii as _binascii
import json as _json
import os as _os
import sys as _sys
import types as _types
"""

_TAIL = r'''
_OUT = _os.dup(1)


def _say(report):
    data = b"\n" + _MARK + _json.dumps(report).encode("ascii") + b"\n"
    while data:
        data = data[_os.write(_OUT, data):]


def _plain(value, depth=0):
    kind = type(value)
    if depth > 50:
        return ["o", "depth"]
    if value is None:
        return ["n"]
    if kind is bool:
        return ["b", value]
    if issubclass(kind, int):
        return ["i", format(int.__int__(value), "x")]
    if issubclass(kind, float):
        return ["f", float.hex(float.__float__(value))]
    if issubclass(kind, complex):
        return ["c", float.hex(complex.real.__get__(value)), float.hex(complex.imag.__get__(value))]
    if issubclass(kind, str):
        return ["s", str.__str__(value)]
    if issubclass(kind, (bytes, bytearray)):
        return ["y", _binascii.b2a_base64(bytes(value), newline=False).decode("ascii")]
    for tag, base in (("l", list), ("t", tuple), ("z", frozenset), ("e", set)):
        if issubclass(kind, base):
            return [tag, [_plain(item, depth + 1) for item in base.__iter__(value)]]
    if issubclass(kind, dict):
        return ["d", [[_plain(k, depth + 1), _plain(v, depth + 1)] for k, v in dict.items(value)]]
    return ["o", kind.__name__[:40]]


def _probe(index, value):
    if _KINDS[index] == "t":
        _say({"p": index, "v": ["b", bool(value)]})
    else:
        _say({"p": index, "v": _plain(value)})


def _main():
    sink = open(_os.devnull, "w")
    _sys.stdout = _sys.stderr = sink  # the learner's own output is not needed here
    module = _types.ModuleType("__main__")
    scope = module.__dict__
    scope["__builtins__"] = __builtins__
    if "__file__" in globals():
        scope["__file__"] = __file__
    _sys.modules["__main__"] = module
    exec(compile(_CODE, "main.py", "exec"), scope)
    scope[_PROBE] = _probe
    exec(compile(_CHECK, "<hidden check>", "exec"), scope)
    _say({"done": 1})


try:
    _main()
except BaseException as error:  # the learner's code or the check stopped early: not passed
    try:
        _say({"error": type(error).__name__[:40]})
    except BaseException:
        pass
    _os._exit(1)
_os._exit(0)
'''


def program(plan, code):
    """The Python program for the sandbox: the learner's *code*, then the probes of *plan*."""
    kinds = "".join(probe.kind for probe in plan.probes)
    return "".join(
        [
            _HEAD,
            f"_MARK = {MARK.encode('ascii')!r}\n",
            f"_PROBE = {PROBE!r}\n",
            f"_KINDS = {kinds!r}\n",
            f"_CODE = {code!r}\n",
            f"_CHECK = {plan.source!r}\n",
            _TAIL,
        ]
    )


# ── reading the run ─────────────────────────────────────────────────────────


def passed(plan, result):
    """Did the sandbox *result* (``execute_python_code``) of ``program(plan, ...)`` pass the check?"""
    if result.get("status") != "success":
        return False
    try:
        reports, done = _read(result.get("output") or "", len(plan.probes))
    except Exception:  # a report line that is not ours: never a pass
        return False
    if not done:
        return False
    for index, probe in enumerate(plan.probes):
        values = reports.get(index)
        if not values or not all(probe.accepts(value) for value in values):
            return False
    return True


def _read(output, count):
    """The reported values by probe number, and whether the check ran to its end."""
    reports, done = {}, False
    for line in output.split("\n"):
        line = line.rstrip("\r")
        if not line.startswith(MARK):
            continue
        report = json.loads(line[len(MARK):])
        if report == {"done": 1}:
            done = True
            continue
        if type(report) is not dict or set(report) != {"p", "v"}:
            raise ValueError("not a probe report")
        index = report["p"]
        if type(index) is not int or not 0 <= index < count:
            raise ValueError("no such probe")
        reports.setdefault(index, []).append(_value(report["v"]))
    return reports, done


class _Opaque:
    """A reported object that is not plain data: equal to nothing, so a comparison with a value fails."""

    __slots__ = ()


_COLLECTIONS = {"l": list, "t": tuple, "e": set, "z": frozenset}


def _value(node, depth=0):
    """Rebuild a reported value from its JSON form; only plain built-in types come out."""
    if depth > 60 or type(node) is not list or not node or type(node[0]) is not str:
        raise ValueError("not a reported value")
    tag, args = node[0], node[1:]
    texts = all(type(arg) is str for arg in args)
    if tag == "n" and not args:
        return None
    if tag == "b" and len(args) == 1 and type(args[0]) is bool:
        return args[0]
    if tag == "i" and len(args) == 1 and texts:
        return int(args[0], 16)
    if tag == "f" and len(args) == 1 and texts:
        return float.fromhex(args[0])
    if tag == "c" and len(args) == 2 and texts:
        return complex(float.fromhex(args[0]), float.fromhex(args[1]))
    if tag == "s" and len(args) == 1 and texts:
        return args[0]
    if tag == "y" and len(args) == 1 and texts:
        return binascii.a2b_base64(args[0].encode("ascii"))
    if tag in _COLLECTIONS and len(args) == 1 and type(args[0]) is list:
        return _COLLECTIONS[tag](_value(item, depth + 1) for item in args[0])
    if tag == "d" and len(args) == 1 and type(args[0]) is list:
        pairs = []
        for pair in args[0]:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError("not a reported value")
            pairs.append((_value(pair[0], depth + 1), _value(pair[1], depth + 1)))
        return dict(pairs)
    if tag == "o" and len(args) == 1 and texts:
        return _Opaque()
    raise ValueError("not a reported value")
