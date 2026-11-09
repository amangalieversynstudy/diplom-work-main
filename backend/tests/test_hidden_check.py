"""Hidden checks: a code step cannot be passed by printing the expected answer.

Matching the printed output alone is not proof: ``print("Charged")`` matches
without any function behind it. A task may carry a ``hidden_check`` that runs
after the learner's code and calls their functions with other values. Programs
are run for real (a local subprocess) so the checks are tested end to end.

The learner's code runs in the same sandbox as the check, so the sandbox never
gets the expected values: it reports what the check's calls returned and the
server compares (game/hidden_checks.py).
"""

import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game import hidden_checks
from game.footprint import finish_code_run
from game.models import CodeRun, Location, Mission, MissionTask, TaskProgress, Track
from game.runner import MAX_OUTPUT_SIZE
from game.services import grade_code_run, public_task_data, run_hidden_check
from game.variants import personalize

User = get_user_model()

pytestmark = pytest.mark.django_db

CHECK = 'assert double(3) == 6\nassert double(0) == 0'
HONEST = "def double(x):\n    return x * 2\n\nprint(double(2))\n"


def _run_locally(code, timeout=5):
    """The sandbox stand-in: a real Python process, UTF-8 on every platform."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "main.py")
        Path(path).write_text(code, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", path],
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
        )
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "output": proc.stdout + proc.stderr,
    }


@pytest.fixture(autouse=True)
def real_runs(monkeypatch):
    """Hidden checks run in a local subprocess instead of Docker."""
    monkeypatch.setattr("game.services.execute_python_code", _run_locally)


@pytest.fixture
def student():
    return User.objects.create_user("student", "student@example.com", "S3cure-pass-1")


@pytest.fixture
def task():
    track = Track.objects.create(slug="t", title="T", is_active=True)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    return MissionTask.objects.create(
        mission=mission,
        order=1,
        task_type="code",
        data={"starter": "x", "expected_output": "4", "hidden_check": CHECK},
    )


def _plain(check=CHECK):
    return SimpleNamespace(data={"expected_output": "4", "hidden_check": check})


# ── the check itself ────────────────────────────────────────────────────────


def test_an_honest_solution_passes():
    assert run_hidden_check(_plain(), HONEST) is True


def test_printing_the_answer_does_not_pass():
    assert run_hidden_check(_plain(), 'print("4")\n') is False


def test_a_solution_that_only_fits_the_example_does_not_pass():
    hardcoded = "def double(x):\n    return 4\n\nprint(double(2))\n"
    assert run_hidden_check(_plain(), hardcoded) is False


@pytest.mark.parametrize("bail_out", ["import sys\nsys.exit(0)\n", "exit()\n", "raise SystemExit\n"])
def test_leaving_early_cannot_skip_the_check(bail_out):
    assert run_hidden_check(_plain(), HONEST + bail_out) is False


def test_a_learner_cannot_forge_the_success_token():
    forged = HONEST + 'print("0" * 32)\nimport sys\nsys.exit(0)\n'
    assert run_hidden_check(_plain(), forged) is False


def test_a_task_without_a_check_always_passes():
    assert run_hidden_check(SimpleNamespace(data={"expected_output": "4"}), "print(4)") is True
    assert run_hidden_check(SimpleNamespace(data={"hidden_check": "   "}), "print(4)") is True


def test_a_failing_check_is_not_a_sandbox_failure(monkeypatch):
    monkeypatch.setattr(
        "game.services.execute_python_code",
        lambda code, timeout=5: {"status": "error", "output": "Timeout: код выполнялся дольше 5 сек."},
    )
    assert run_hidden_check(_plain(), HONEST) is False


def test_a_broken_sandbox_is_reported_as_unknown(monkeypatch):
    monkeypatch.setattr(
        "game.services.execute_python_code",
        lambda code, timeout=5: {"status": "error", "output": "Ошибка песочницы", "infra": True},
    )
    assert run_hidden_check(_plain(), HONEST) is None


def test_a_stored_check_that_does_not_compile_fails_without_an_error(monkeypatch):
    calls = []
    monkeypatch.setattr("game.services.execute_python_code", lambda code, timeout=5: calls.append(code))
    assert run_hidden_check(_plain("assert ("), HONEST) is False
    assert calls == []


# ── nothing in the sandbox gives the answer away ────────────────────────────


def _program(check, code="pass\n"):
    return hidden_checks.program(hidden_checks.compile_check(check), code)


def test_the_sandbox_gets_the_calls_but_never_the_expected_values():
    program = _program(
        'assert spell(30) == "Zephyrion"\n'
        "assert total(7) == 7 * (7 + 1) // 2\n"
        "assert pick([3, 1]) in (31, 47)\n"
        "assert 1913 == year()\n"
    )
    for call in ("spell(30)", "total(7)", "pick([3, 1])", "year()"):
        assert call in program
    for answer in ("Zephyrion", "7 * (7 + 1) // 2", "28", "31", "47", "1913"):
        assert answer not in program


def test_the_program_runs_on_the_sandboxs_python_38():
    """Judge0 CE runs Python 3.8 (language 71): the program must not use newer syntax."""
    check = 'h = Hero("x", 5)\nassert h.hp == 5 and h.alive()\nassert f"{h.hp}" == "5"\n'
    ast.parse(_program(check, "class Hero: pass\n"), feature_version=(3, 8))


# ── the old ways to fake a pass ─────────────────────────────────────────────
# The check used to run in the learner's process and pass on a token printed at its end.

READ_OWN_PROGRAM = [
    "open(sys.argv[0], encoding='utf-8').read()",
    "open(__file__, encoding='utf-8').read()",
]


def _attacked(code, check=CHECK):
    """Run *code* with the check; the run must end with the attack's own exit(0), or it proves nothing."""
    plan = hidden_checks.compile_check(check)
    result = _run_locally(hidden_checks.program(plan, code))
    assert result["status"] == "success", result["output"]
    return hidden_checks.passed(plan, result)


@pytest.mark.parametrize("read", READ_OWN_PROGRAM)
def test_reading_the_program_and_printing_its_tokens_does_not_pass(read):
    """Everything that looks like a token goes to the real stdout, then the run ends at once."""
    attack = (
        "import os, re, sys\n"
        f"source = {read}\n"
        "found = re.findall(r'[0-9a-f]{32}', source)\n"
        "os.write(1, ('\\n'.join(found) + '\\n').encode())\n"
        "print(*found)\n"
        "os._exit(0)\n"
    )
    assert _attacked(HONEST + attack) is False


@pytest.mark.parametrize("read", READ_OWN_PROGRAM)
def test_echoing_the_whole_program_does_not_pass(read):
    attack = f"import os, sys\nos.write(1, {read}.encode())\nos._exit(0)\n"
    assert _attacked(HONEST + attack) is False


def _forger(*reports):
    """Learner code that writes report lines of its own and leaves before the check runs."""
    payload = "".join("\n" + hidden_checks.MARK + json.dumps(r) + "\n" for r in reports).encode()
    return f"import os\nos.write(1, {payload!r})\nos._exit(0)\n"


@pytest.mark.parametrize(
    "reports",
    [
        [{"done": 1}],
        [{"p": 0, "v": ["b", True]}, {"p": 1, "v": ["b", True]}, {"done": 1}],
        # the inputs of the calls are in the program; the answers are not
        [{"p": 0, "v": ["i", "3"]}, {"p": 1, "v": ["i", "0"]}, {"done": 1}],
    ],
)
def test_reports_written_by_the_learner_do_not_pass(reports):
    assert _attacked(HONEST + _forger(*reports)) is False


def test_a_wrong_report_next_to_the_real_one_fails():
    wrong_first = _forger({"p": 0, "v": ["i", "7"]}).replace("os._exit(0)\n", "")
    assert run_hidden_check(_plain(), wrong_first + HONEST) is False


def test_an_object_that_equals_everything_does_not_pass():
    look_alike = (
        "class Anything:\n"
        "    def __eq__(self, other):\n"
        "        return True\n"
        "    __hash__ = object.__hash__\n\n"
        "def double(x):\n"
        "    return Anything()\n\n"
        "print(4)\n"
    )
    assert run_hidden_check(_plain(), look_alike) is False


def test_leaving_from_inside_the_learners_function_does_not_pass():
    bail = "import sys\n\ndef double(x):\n    sys.exit(0)\n\nprint(4)\n"
    assert run_hidden_check(_plain(), bail) is False


def test_the_learner_cannot_take_the_name_the_check_calls():
    hijack = HONEST + f"{hidden_checks.PROBE} = lambda *args: None\n"
    assert run_hidden_check(_plain(), hijack) is True  # the check's own one replaces it


# ── honest solutions grade as before ────────────────────────────────────────


def _in_process(code, check):
    """How the check grades *code* when both simply run in one namespace (trusted test code)."""
    scope = {"__name__": "__main__"}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, scope)  # noqa: S102 - the solutions below are this file's own
            exec(check, scope)  # noqa: S102
    except BaseException:  # noqa: BLE001 - any stop is a failed check
        return False
    return True


SOLUTIONS_OF_DOUBLE = {
    "right": "def double(x):\n    return x * 2\n",
    "float": "def double(x):\n    return x * 2.0\n",
    "wrong": "def double(x):\n    return x * 3\n",
    "text": "def double(x):\n    return str(x * 2)\n",
    "raises": "def double(x):\n    raise ValueError(x)\n",
    "missing": "print(4)\n",
}

CHECKS_OF_DOUBLE = [
    "assert double(3) == 6",
    "assert 6 == double(3)",
    "assert double(2) != 5",
    "assert double(1) < 3 and double(1) <= 2",
    "assert double(2) > 3 and double(2) >= 4",
    "assert double(2) in (4, 8)",
    "assert 3 not in [double(1), double(2)]",
    "assert double(0) is not None",
    "assert isinstance(double(1), int)",
    "assert double(double(1)) == 4 and double(-1) == -2",
    "x = double(5)\nassert x == 10\nfor n in range(3):\n    assert double(n) == n + n",
]


@pytest.mark.parametrize("check", CHECKS_OF_DOUBLE)
@pytest.mark.parametrize("name", sorted(SOLUTIONS_OF_DOUBLE))
def test_the_verdict_is_the_one_python_itself_gives(name, check):
    code = SOLUTIONS_OF_DOUBLE[name]
    assert run_hidden_check(_plain(check), code) is _in_process(code, check)


@pytest.mark.parametrize(
    "code",
    [
        "def word_count(text):\n    return {w: text.split().count(w) for w in text.split()}\n",
        "from collections import Counter\n\ndef word_count(text):\n    return Counter(text.split())\n",
        "from collections import defaultdict\n\ndef word_count(text):\n"
        "    counts = defaultdict(int)\n    for w in text.split():\n        counts[w] += 1\n    return counts\n",
        "from collections import OrderedDict\n\ndef word_count(text):\n"
        "    return OrderedDict((w, text.split().count(w)) for w in sorted(set(text.split())))\n",
    ],
)
def test_dict_like_results_compare_like_dicts(code):
    check = 'assert word_count("a b a") == {"a": 2, "b": 1}\nassert word_count("") == {}'
    assert run_hidden_check(_plain(check), code) is True


def test_other_built_in_kinds_of_values_compare_as_in_python():
    code = (
        "from collections import namedtuple\nfrom enum import IntEnum\n\n"
        "Point = namedtuple('Point', 'x y')\n\nclass Level(IntEnum):\n    HIGH = 3\n\n"
        "def point():\n    return Point(1, 2)\n\ndef level():\n    return Level.HIGH\n\n"
        "def shape():\n    return {'sides': frozenset({1, 2}), 'name': b'sq', 'z': 1 + 2j, 'n': None}\n"
    )
    check = (
        "assert point() == (1, 2)\nassert level() == 3\nassert level() > 2\n"
        "assert shape() == {'sides': {1, 2}, 'name': b'sq', 'z': 1 + 2j, 'n': None}\n"
        "assert sorted(shape()['sides']) == [1, 2]\nassert 2 ** 70 == 2 ** 70 + point()[0] - 1\n"
    )
    assert _in_process(code, check) is True
    assert run_hidden_check(_plain(check), code) is True


def test_the_learners_module_behaves_like_a_script():
    code = (
        "from dataclasses import dataclass\n\n@dataclass\nclass Hero:\n    name: str\n    hp: int = 10\n\n"
        "def make(name):\n    return Hero(name)\n\n"
        "if __name__ == '__main__':\n    import __main__\n    READY = __main__.make('a').hp\n"
    )
    check = 'assert READY == 10\nassert make("b") == Hero("b")\nassert make("c").name == "c"'
    assert run_hidden_check(_plain(check), code) is True


def test_a_check_that_wants_an_error_still_gets_it():
    check = (
        "assert safe_divide(9, 3) == 3\ntry:\n    safe_divide('a', 2)\nexcept TypeError:\n    pass\n"
        "else:\n    raise AssertionError('TypeError must not be swallowed')"
    )
    careful = "def safe_divide(a, b):\n    try:\n        return a / b\n    except ZeroDivisionError:\n        return None\n"
    swallowing = careful.replace("except ZeroDivisionError", "except Exception")
    assert run_hidden_check(_plain(check), careful) is True
    assert run_hidden_check(_plain(check), swallowing) is False


def test_a_long_printout_no_longer_hides_the_result(monkeypatch):
    """The sandbox keeps only MAX_OUTPUT_SIZE of output; the learner's own printing is not part of it."""

    def capped(code, timeout=5):
        result = _run_locally(code, timeout)
        result["output"] = result["output"][:MAX_OUTPUT_SIZE]
        return result

    monkeypatch.setattr("game.services.execute_python_code", capped)
    chatty = HONEST + "for i in range(20000):\n    print('the dragon sleeps', i)\n"
    assert run_hidden_check(_plain(), chatty) is True


def test_the_check_text_keeps_its_layout():
    """Several statements on a line, an assert over several lines, a comment, a decorator, non-ASCII."""
    check = (
        'import functools; assert shout("ёж") == "ЁЖ!"  # a comment\n'
        "assert shout(\n    'a',  # inner comment\n) == 'A!', 'shout must add !'\n"
        "@functools.lru_cache(None)\ndef twice(s):\n    return shout(s) * 2\n"
        "assert twice('b') == 'B!B!'\n"
    )
    code = "def shout(s):\n    return s.upper() + '!'\n"
    assert run_hidden_check(_plain(check), code) is True
    assert run_hidden_check(_plain(check), code.replace("+ '!'", "+ '?'")) is False


# ── what the server accepts from a run ──────────────────────────────────────


def _report(*reports, status="success"):
    lines = "".join("\n" + hidden_checks.MARK + json.dumps(r) + "\n" for r in reports)
    return {"status": status, "output": "noise\n" + lines}


TWO = hidden_checks.compile_check("assert double(3) == 6\nassert isinstance(double(1), int)")
RIGHT = ({"p": 0, "v": ["i", "6"]}, {"p": 1, "v": ["b", True]}, {"done": 1})


def test_well_formed_right_reports_pass():
    assert hidden_checks.passed(TWO, _report(*RIGHT)) is True
    assert hidden_checks.passed(TWO, _report(RIGHT[0], *RIGHT)) is True  # the same right value twice


@pytest.mark.parametrize(
    "run",
    [
        _report(*RIGHT, status="error"),
        _report(*RIGHT[:2]),  # the check did not reach its end
        _report(RIGHT[0], RIGHT[2]),  # a probe never reported
        _report({"p": 0, "v": ["i", "7"]}, *RIGHT),  # one of two reports is wrong
        _report(*RIGHT, {"p": 2, "v": ["n"]}),  # nobody asked for probe 2
        _report(*RIGHT, {"p": True, "v": ["n"]}),
        _report({"p": 0, "v": ["i", "6"]}, {"p": 1, "v": ["i", "1"]}, RIGHT[2]),  # 1 is not True
        _report({"p": 0, "v": ["o", "Anything"]}, RIGHT[1], RIGHT[2]),
        _report({"p": 0, "v": ["s", "6"]}, RIGHT[1], RIGHT[2]),
        _report(*RIGHT, {"error": "SystemExit"}),
        {"status": "success", "output": hidden_checks.MARK + "{not json\n"},
        {"status": "success", "output": hidden_checks.MARK + '{"p": 0, "v": ' + "[" * 5000 + "]" * 5000 + "}\n"},
        {"status": "success", "output": hidden_checks.MARK + '{"p": 0, "v": ["i", "' + "f" * 40000 + '"]}\n'},
        {"status": "success", "output": hidden_checks.MARK + '{"p": 0, "v": ["e", [["l", []]]]}\n'},
        {"status": "success", "output": ""},
    ],
)
def test_anything_else_fails_quietly(run):
    assert hidden_checks.passed(TWO, run) is False


def test_a_float_report_compares_like_python():
    assert hidden_checks.passed(TWO, _report({"p": 0, "v": ["f", (6.0).hex()]}, *RIGHT[1:])) is True


# ── how a check is split into probes ────────────────────────────────────────


def test_value_and_truth_probes():
    plan = hidden_checks.compile_check(
        "h = Hero(5)\n"
        "assert h.hp == 5 and h.alive()\n"
        "assert result is None\n"
        "assert result is 5\n"
        "assert f(1) == f(1)\n"
        "assert 0 < g() < 9\n"
        "assert names() == [n for n in 'ab']\n"
        "for n in range(2):\n    assert g(n) == 1\n"
    )
    assert [p.kind for p in plan.probes] == ["v", "t", "v", "t", "t", "t", "t"]
    assert plan.probes[0].expected == 5 and plan.probes[2].expected is None
    assert "for n in range(2):\n    assert g(n) == 1" in plan.source  # nested asserts run as written
    assert not plan.weak
    assert hidden_checks.compile_check("assert isinstance(m, Hero)").weak
    assert hidden_checks.compile_check("h = 1").weak


# ── grading ─────────────────────────────────────────────────────────────────


def test_grading_passes_an_honest_solution(student, task):
    verdict = grade_code_run(student, task, HONEST, "4\n", 0)
    assert verdict["passed"] is True
    assert verdict["hidden_failed"] is False
    assert verdict["progress"]["status"] == "completed"


def test_grading_rejects_right_output_without_the_function(student, task):
    verdict = grade_code_run(student, task, 'print("4")', "4\n", 0)
    assert verdict["passed"] is False
    assert verdict["hidden_failed"] is True
    assert verdict["progress"]["status"] == "in_progress"
    assert verdict["progress"]["attempts"] == 1


def test_the_hidden_check_only_runs_when_the_visible_output_is_right(student, task, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "game.services.execute_python_code", lambda code, timeout=5: calls.append(code)
    )
    verdict = grade_code_run(student, task, "print('nope')", "nope\n", 0)
    assert verdict["passed"] is False
    assert verdict["hidden_failed"] is False
    assert calls == []


def test_a_broken_sandbox_does_not_cost_an_attempt(student, task, monkeypatch):
    monkeypatch.setattr(
        "game.services.execute_python_code",
        lambda code, timeout=5: {"status": "error", "output": "boom", "infra": True},
    )
    assert grade_code_run(student, task, HONEST, "4\n", 0) is None
    assert not TaskProgress.objects.filter(user=student, task=task).exists()

    verdict = finish_code_run(
        student, task, code=HONEST, stdout="4\n", stderr="", exit_code=0,
        duration=0.1, reasons=set(),
    )
    assert verdict is None
    assert not TaskProgress.objects.filter(user=student, task=task).exists()
    run = CodeRun.objects.get(user=student, task=task)
    assert run.outcome == "runner_error"


# ── the key stays on the server ─────────────────────────────────────────────


def test_learners_never_receive_the_check(student, task):
    assert "hidden_check" not in public_task_data(task)
    api = APIClient()
    api.force_authenticate(student)
    mission = task.mission
    response = api.get(f"/api/missions/{mission.pk}/")
    assert response.status_code == 200
    assert "hidden_check" not in json.dumps(response.json())
    assert "double(3)" not in json.dumps(response.json())


# ── Studio ──────────────────────────────────────────────────────────────────


def _teacher_task(api, mission, **data):
    return api.post(
        "/api/teacher/studio/tasks/",
        {
            "mission": mission.pk,
            "task_type": "code",
            "title_ru": "Шаг",
            "order": 1,
            "data": {"starter": "", "expected_output": "4", **data},
        },
        format="json",
    )


@pytest.fixture
def teacher_api():
    teacher = User.objects.create_user(username="teacher", password="TestPass123!", is_staff=True)
    track = Track.objects.create(slug="tt", title="T", owner=teacher)
    location = Location.objects.create(track=track, title="Section")
    mission = Mission.objects.create(location=location, title="Mission", is_active=False)
    api = APIClient()
    api.force_authenticate(teacher)
    return api, mission


def test_a_teacher_can_author_and_read_back_a_check(teacher_api):
    api, mission = teacher_api
    response = _teacher_task(api, mission, hidden_check=CHECK)
    assert response.status_code == 201, response.content
    assert response.json()["data"]["hidden_check"] == CHECK


def test_a_check_that_does_not_compile_is_refused(teacher_api):
    api, mission = teacher_api
    response = _teacher_task(api, mission, hidden_check="assert (")
    assert response.status_code == 400
    assert "не компилируется" in json.dumps(response.json(), ensure_ascii=False)


def test_an_empty_check_is_not_stored(teacher_api):
    api, mission = teacher_api
    response = _teacher_task(api, mission, hidden_check="   ")
    assert response.status_code == 201
    assert "hidden_check" not in response.json()["data"]


# ── the built-in course ─────────────────────────────────────────────────────

FIXTURES = [
    Path(__file__).resolve().parents[1] / "game" / "fixtures" / name
    for name in ("intro_course.json", "python_continued.json")
]

# what a correct learner writes in place of ``raise NotImplementedError`` (per step)
SOLUTIONS = {
    22: 'if mana > 100:\n    return "Overcharged"\nif mana >= 50:\n    return "Charged"\nreturn "Low"',
    32: "total += i",
    42: "result *= base",
    52: 'return name.upper() + "!"',
    62: "if n > 10:\n    count += 1",
    72: "total += gold",
    81: 'best = max(heroes, key=lambda h: h["hp"])\nreturn f"Champion: {best[\'name\']} ({best[\'hp\']})"',
    # the second course
    92: 'return "".join(word[0].upper() + "." for word in full_name.split())',
    102: "return len(set(items))",
    112: "try:\n    return a / b\nexcept ZeroDivisionError:\n    return None",
    122: "return [n * n for n in numbers if n % 2 == 0]",
    132: "counts = {}\nfor word in text.lower().split():\n    counts[word] = counts.get(word, 0) + 1\nreturn counts",
    142: "self.hp = max(0, self.hp - damage)",
    152: "super().__init__(name, hp)\nself.mana = mana",
    162: 'report = {}\nfor hero in heroes:\n    report[hero["class"]] = report.get(hero["class"], 0) + hero["hp"]\nreturn report',
}


def _course_tasks():
    tasks = {}
    for fixture in FIXTURES:
        for row in json.loads(fixture.read_text(encoding="utf-8")):
            if row["model"] == "game.missiontask" and row["pk"] in SOLUTIONS:
                # a step with personal variants is checked on its first variant (see test_course_variants)
                task = MissionTask(pk=row["pk"], data=row["fields"]["data"])
                tasks[row["pk"]] = personalize(task, None).data
    return tasks


def _solved(pk, starter):
    def fill(match):
        indent = match.group(1)
        return "\n".join(indent + line for line in SOLUTIONS[pk].split("\n"))

    return re.sub(r"^([ \t]*)raise NotImplementedError\(.*\)$", fill, starter, flags=re.M)


def _stdout(code):
    return _run_locally(code)["output"].strip()


@pytest.mark.parametrize("pk", sorted(SOLUTIONS))
def test_every_function_step_of_the_course_has_a_working_check(pk):
    data = _course_tasks()[pk]
    task = SimpleNamespace(data=data)
    expected = data["expected_output"]

    assert data["hidden_check"], "the step has no hidden check"
    compile(data["hidden_check"], "<check>", "exec")
    # at least one call is compared with a value on the server, not only reported as yes/no
    assert not hidden_checks.compile_check(data["hidden_check"]).weak

    # the starter is unfinished: it must not pass
    assert run_hidden_check(task, data["starter"]) is False

    # a correct solution prints the expected text and passes the check
    solution = _solved(pk, data["starter"])
    assert _stdout(solution) == expected
    assert run_hidden_check(task, solution) is True

    # printing the expected text is exactly what the check exists to stop
    assert run_hidden_check(task, f"print({expected!r})\n") is False


# ── the sandbox reports a timeout as the learner's fault, not as a broken sandbox ──


@pytest.mark.parametrize(
    "error",
    [
        __import__("requests").exceptions.ReadTimeout("slow"),
        __import__("urllib3").exceptions.ReadTimeoutError(None, "/wait", "slow"),
        __import__("requests").exceptions.ConnectionError(
            "NpipeHTTPConnectionPool(host='localhost', port=None): Read timed out."
        ),
    ],
)
def test_a_wait_timeout_is_not_an_infrastructure_failure(error):
    from unittest.mock import MagicMock, patch

    from game import runner

    container = MagicMock()
    container.wait.side_effect = error
    client = MagicMock()
    client.containers.run.return_value = container
    with patch.object(runner.docker, "from_env", return_value=client):
        result = runner.execute_python_code("while True: pass", timeout=1)
    assert "infra" not in result
    assert result["output"].startswith("Timeout")
    container.kill.assert_called_once()
    container.remove.assert_called_once()


def test_other_sandbox_errors_stay_infrastructure_failures():
    from unittest.mock import MagicMock, patch

    from game import runner

    client = MagicMock()
    client.containers.run.side_effect = RuntimeError("daemon exploded")
    with patch.object(runner.docker, "from_env", return_value=client):
        result = runner.execute_python_code("print(1)")
    assert result["infra"] is True


def test_every_code_step_of_every_course_is_covered_by_a_reference_solution():
    """A new code step without a hidden check (or without a reference solution
    to prove the check works) must not slip into the built-in courses."""
    code_steps = []
    for fixture in FIXTURES:
        for row in json.loads(fixture.read_text(encoding="utf-8")):
            if row["model"] == "game.missiontask" and row["fields"]["task_type"] == "code":
                if row["fields"]["data"].get("expected_output"):
                    code_steps.append(row["pk"])
    assert sorted(code_steps) == sorted(SOLUTIONS)


# ── Windows named pipes report the end of the stream as an error, not as EOF ──


class _PipeClosed(Exception):
    """Stands in for pywintypes.error(109, "ReadFile", ...): not an OSError."""


class _FakeSocket:
    def __init__(self, chunks, error):
        self._chunks = list(chunks)
        self._error = error

    def settimeout(self, _value):
        pass

    def recv(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        raise self._error

    def close(self):
        pass


def _stream_with(error):
    import struct
    from unittest.mock import MagicMock, patch

    from game import runner

    payload = "Привет\n".encode()
    frame = struct.pack(">BBBBI", 1, 0, 0, 0, len(payload)) + payload
    container = MagicMock()
    container.status = "exited"
    container.wait.return_value = {"StatusCode": 0}
    client = MagicMock()
    client.containers.create.return_value = container
    client.api.attach_socket.return_value = _FakeSocket([frame], error)
    with patch.object(runner.docker, "from_env", return_value=client):
        return list(runner.stream_python_code("print(1)", timeout=5))


def test_a_closed_windows_pipe_is_the_end_of_the_output_not_a_sandbox_failure():
    events = _stream_with(_PipeClosed(109, "ReadFile", "The pipe has been ended."))
    kinds = [e["type"] for e in events]
    assert kinds == ["stdout", "exit"]
    assert events[0]["data"] == "Привет\n"
    assert events[-1]["code"] == 0


def test_other_socket_errors_are_still_reported_as_a_sandbox_failure():
    events = _stream_with(_PipeClosed(5, "ReadFile", "Access is denied."))
    assert any(e.get("reason") == "runner_error" for e in events if e["type"] == "error")
    assert events[-1]["code"] == -1


# ── help texts of the built-in courses ──────────────────────────────────────


def _code_steps():
    steps = {}
    for fixture in FIXTURES:
        for row in json.loads(fixture.read_text(encoding="utf-8")):
            if row["model"] == "game.missiontask" and row["fields"]["task_type"] == "code":
                steps[row["pk"]] = row["fields"]["data"]
    return steps


def test_every_code_step_has_hints_in_both_languages():
    for pk, data in _code_steps().items():
        hints = data.get("hints") or []
        assert hints, f"step {pk} has no hints"
        for hint in hints:
            assert hint.get("ru") and hint.get("en"), f"step {pk}: a hint is missing a language"


def test_outlines_exist_in_both_languages_and_are_valid_python():
    for pk, data in _code_steps().items():
        skeleton = data.get("skeleton")
        if pk == 12:  # the first spell needs no outline
            assert not skeleton
            continue
        assert skeleton and skeleton.get("ru") and skeleton.get("en"), f"step {pk} has no outline"
        for text in skeleton.values():
            compile(text, f"<outline {pk}>", "exec")


def test_hints_and_outlines_never_contain_the_solution():
    steps = _code_steps()
    for pk, body in SOLUTIONS.items():
        data = steps[pk]
        texts = [h[lang] for h in data.get("hints", []) for lang in ("ru", "en")]
        # an outline may name the outputs in its comments (the task text does too),
        # but its code lines must not be the solution
        for outline in (data.get("skeleton") or {}).values():
            texts += [ln for ln in outline.split("\n") if not ln.strip().startswith("#")]
        combined = "\n".join(texts)
        for line in body.split("\n"):
            line = line.strip()
            # "return report" is also plain English ("do not forget to return report")
            if re.fullmatch(r"return \w+", line):
                continue
            if len(line) >= 10 and not line.startswith(("try:", "except", "for ")):
                assert line not in combined, f"step {pk}: the help gives away {line!r}"
