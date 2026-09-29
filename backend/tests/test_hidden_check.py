"""Hidden checks: a code step cannot be passed by printing the expected answer.

Matching the printed output alone is not proof: ``print("Charged")`` matches
without any function behind it. A task may carry a ``hidden_check`` that runs
after the learner's code and calls their functions with other values. Programs
are run for real (a local subprocess) so the checks are tested end to end.
"""

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

from game.footprint import finish_code_run
from game.models import CodeRun, Location, Mission, MissionTask, TaskProgress, Track
from game.services import grade_code_run, public_task_data, run_hidden_check

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
                tasks[row["pk"]] = row["fields"]["data"]
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
