"""What student code is made of (constructs) and its structural fingerprint; the code itself is never kept."""

import json
from pathlib import Path

import pytest
from rest_framework import serializers

from game.codeanalysis import CONSTRUCTS, analyse
from game.studio import _clean_not_yet


@pytest.mark.parametrize(
    "code, expected",
    [
        ("print(1)", []),
        ("def f():\n    return 1\n", ["def"]),
        ("f = lambda x: x\n", ["lambda"]),
        ("a = [i for i in range(3)]\n", ["comprehension"]),
        ("a = {i: i for i in range(3)}\n", ["comprehension"]),
        ("try:\n    pass\nexcept ValueError:\n    pass\n", ["try"]),
        ("import math\nfrom os import path\n", ["import"]),
        ("class A:\n    pass\n", ["class"]),
        ("with open('f') as h:\n    pass\n", ["with"]),
        ("def f():\n    return [x for x in []]\n", ["comprehension", "def"]),
    ],
)
def test_constructs_are_found(code, expected):
    assert analyse(code)["constructs"] == expected


def test_code_that_does_not_parse_has_no_analysis():
    assert analyse("print(") is None
    assert analyse("def :\n") is None


def test_the_same_program_with_other_names_has_the_same_fingerprint():
    a = "total = 0\nfor n in range(5):\n    total += n\nprint(total)\n"
    b = "# sum them\nacc = 0\nfor i in range(5):\n    acc += i\nprint(acc)\n"
    assert analyse(a)["fingerprint"] == analyse(b)["fingerprint"]


def test_functions_arguments_and_docstrings_do_not_change_it():
    a = 'def area(w, h):\n    """Area."""\n    return w * h\nprint(area(2, 3))\n'
    b = "def rect(a, b):\n    return a * b\nprint(rect(2, 3))\n"
    assert analyse(a)["fingerprint"] == analyse(b)["fingerprint"]


def test_different_structure_or_constants_differ():
    base = "x = 1\nprint(x + 1)\n"
    assert analyse(base)["fingerprint"] != analyse("x = 1\nprint(x * 1)\n")["fingerprint"]
    assert analyse(base)["fingerprint"] != analyse("x = 2\nprint(x + 1)\n")["fingerprint"]


def test_builtins_keep_their_meaning():
    # print and len are not the author's names: swapping them is a different program
    assert analyse("print(1)\n")["fingerprint"] != analyse("len(1)\n")["fingerprint"]


def test_the_analysis_holds_no_code():
    result = analyse("secret_value = 'hunter2'\nprint(secret_value)\n")
    assert set(result) == {"fingerprint", "nodes", "constructs"}
    assert "hunter2" not in str(result)
    assert result["nodes"] > 5


# ── Studio ─────────────────────────────────────────────────────────────────


def test_studio_accepts_known_constructs_once():
    assert _clean_not_yet(["try", "lambda", "try", " "]) == ["try", "lambda"]
    assert _clean_not_yet(None) == [] and _clean_not_yet([]) == []


@pytest.mark.parametrize("bad", [["goto"], "try", {"a": 1}])
def test_studio_rejects_unknown_or_malformed(bad):
    with pytest.raises(serializers.ValidationError):
        _clean_not_yet(bad)


# ── the two built-in courses ───────────────────────────────────────────────

FIXTURES = Path(__file__).resolve().parents[1] / "game" / "fixtures"


def _code_steps():
    for name in ("intro_course.json", "python_continued.json"):
        for obj in json.loads((FIXTURES / name).read_text(encoding="utf-8")):
            if obj["model"] == "game.missiontask" and obj["fields"]["task_type"] == "code":
                yield obj


@pytest.mark.parametrize("step", list(_code_steps()), ids=lambda o: f"task{o['pk']}")
def test_a_step_never_marks_as_untaught_what_its_own_starter_or_skeleton_uses(step):
    data = step["fields"]["data"]
    marked = set(data.get("not_yet", []))
    assert marked <= set(CONSTRUCTS)
    shown = [data.get("starter", "")] + [(data.get("skeleton") or {}).get(k, "") for k in ("ru", "en")]
    used = set()
    for code in shown:
        used |= set((analyse(code) or {}).get("constructs", []))
    assert not (marked & used)
