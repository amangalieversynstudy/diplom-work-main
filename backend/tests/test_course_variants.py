"""Every personal variant of the built-in courses has a consistent key.

For each variant of each step the reference solution is run on the learner's own starter: it has to print
exactly the variant's expected output and to pass the hidden check. A typo in a variant (a wrong total, a
mismatch between the text and the call) would otherwise be found by a learner.
"""

import contextlib
import io
import json
import re
from pathlib import Path

import pytest

from game.models import MissionTask
from game.variants import personalize, variant_index, variants_of

FIXTURES = Path(__file__).resolve().parents[1] / "game" / "fixtures"

# what replaces the ``raise NotImplementedError(...)`` line of the starter (indentation is added)
REFERENCE = {
    22: 'if mana > 100:\n    return "Overcharged"\nif mana >= 50:\n    return "Charged"\nreturn "Low"',
    32: "total += i",
    42: "result *= base",
    52: 'return name.upper() + "!"',
    62: "if n > 10:\n    count += 1",
    72: "total += gold",
    92: 'return ".".join(word[0].upper() for word in full_name.split()) + "."',
    102: "return len(set(items))",
    122: "return [n * n for n in numbers if n % 2 == 0]",
}


def _all_steps():
    for name in ("intro_course.json", "python_continued.json"):
        for obj in json.loads((FIXTURES / name).read_text(encoding="utf-8")):
            if obj["model"] == "game.missiontask" and variants_of(obj["fields"].get("data", {})):
                yield obj


def _steps():
    return (obj for obj in _all_steps() if obj["fields"]["task_type"] == "code")


def _explain_steps():
    return (obj for obj in _all_steps() if obj["fields"]["data"].get("kind") == "explain")


def _cases():
    for obj in _steps():
        for index in range(len(obj["fields"]["data"]["variants"])):
            yield pytest.param(obj, index, id=f"task{obj['pk']}-variant{index}")


def _task(obj):
    fields = obj["fields"]
    return MissionTask(
        pk=obj["pk"],
        task_type="code",
        title_ru=fields["title_ru"],
        title_en=fields["title_en"],
        body_ru=fields["body_ru"],
        body_en=fields["body_en"],
        data=fields["data"],
    )


def _solved(starter, replacement):
    out = []
    for line in starter.splitlines():
        if line.strip().startswith("raise NotImplementedError"):
            indent = line[: len(line) - len(line.lstrip())]
            out.extend(indent + part for part in replacement.splitlines())
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def test_nine_steps_have_variants():
    assert sorted(obj["pk"] for obj in _steps()) == sorted(REFERENCE)


@pytest.mark.parametrize("obj, index", list(_cases()))
def test_the_reference_solution_matches_the_variant_key(obj, index):
    task = _task(obj)
    count = len(obj["fields"]["data"]["variants"])
    uid = next(u for u in range(1, 5000) if variant_index(u, task.pk, count) == index)
    mine = personalize(task, uid)

    # the text, the starter and the key all speak about the same variant
    assert "{{" not in mine.body_ru and "{{" not in mine.body_en and "{{" not in mine.title_ru
    assert "{{" not in mine.data["starter"] and "{{" not in mine.data["expected_output"]
    assert "{{" not in (mine.data.get("hidden_check") or "")
    for text in (mine.body_ru, mine.body_en):
        assert re.search(re.escape(mine.data["expected_output"]), text), "the text must show the expected output"

    program = _solved(mine.data["starter"], REFERENCE[task.pk])
    namespace = {}
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        exec(program, namespace)  # trusted reference code from this test file
    assert printed.getvalue().strip() == mine.data["expected_output"].strip()
    check = mine.data.get("hidden_check")
    if check:
        exec(check, namespace)


# ── "explain your solution": a question about the learner's own program ────

def _answer(about, vars_):
    """The right answer to the explain question of code step *about*, worked out from the task's spec."""
    import ast

    if about == 22:
        mana = vars_["probe"]
        return "Overcharged" if mana > 100 else "Charged" if mana >= 50 else "Low"
    if about == 32:
        return vars_["n"]
    if about == 42:
        return vars_["base"] ** 2
    if about == 52:
        return len(vars_["name"]) + 1
    if about == 62:
        return sum(1 for n in ast.literal_eval(vars_["numbers"]) if n > vars_["t"])
    if about == 72:
        return len(ast.literal_eval(vars_["heroes"]))
    if about == 92:
        return len(vars_["name"].split())
    if about == 102:
        return len(set(ast.literal_eval(vars_["items"])))
    if about == 122:
        return sum(1 for n in ast.literal_eval(vars_["numbers"]) if n % 2 == 0)
    raise AssertionError(about)


def _explain_cases():
    for obj in _explain_steps():
        for index in range(len(obj["fields"]["data"]["variants"])):
            yield pytest.param(obj, index, id=f"task{obj['pk']}-variant{index}")


def test_every_personalised_code_step_has_an_explain_question():
    code = {obj["pk"]: obj for obj in _steps()}
    explain = {obj["fields"]["data"]["about"]: obj for obj in _explain_steps()}
    assert sorted(explain) == sorted(code)
    for about, obj in explain.items():
        fields = obj["fields"]
        assert fields["mission"] == code[about]["fields"]["mission"]
        assert fields["order"] > code[about]["fields"]["order"]
        assert fields["task_type"] == "quiz" and fields["is_required"] is True


@pytest.mark.parametrize("obj, index", list(_explain_cases()))
def test_the_explain_key_is_the_right_answer_and_the_options_are_fair(obj, index):
    data = obj["fields"]["data"]
    task = _task(obj)
    count = len(data["variants"])
    uid = next(u for u in range(1, 5000) if variant_index(u, task.pk, count) == index)
    mine = personalize(task, uid)
    assert "{{" not in mine.body_ru and "{{" not in mine.body_en
    values = [option["value"] for option in mine.data["options"]]
    assert len(values) == 4 and len(set(values)) == 4
    assert mine.data["correct_answer"] in values
    assert mine.data["correct_answer"] == str(_answer(data["about"], data["variants"][index]["vars"]))
    assert all(option["value"] == option["label"] for option in mine.data["options"])
