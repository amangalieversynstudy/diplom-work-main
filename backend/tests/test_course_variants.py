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


def _steps():
    for name in ("intro_course.json", "python_continued.json"):
        for obj in json.loads((FIXTURES / name).read_text(encoding="utf-8")):
            if obj["model"] == "game.missiontask" and variants_of(obj["fields"].get("data", {})):
                yield obj


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
