"""Help after repeated failures, and the teacher's early-warning list."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.footprint import finish_code_run
from game.models import (
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)
from game.runner import REASON_UNAVAILABLE
from game.services import HELP_AFTER_FAILURES

User = get_user_model()

pytestmark = pytest.mark.django_db

WARNING_URL = "/api/analytics/early-warning/"


def _user(name, **extra):
    return User.objects.create_user(username=name, password="TestPass123!", **extra)


def _client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


@pytest.fixture
def teacher():
    return _user("teacher", is_staff=True)


@pytest.fixture
def course(teacher):
    track = Track.objects.create(slug="py", title="Python", is_active=True, owner=teacher)
    location = Location.objects.create(track=track, title="Island", order=1)
    mission = Mission.objects.create(location=location, title="Basics", order=1)
    quiz = MissionTask.objects.create(
        mission=mission,
        order=1,
        task_type="quiz",
        title="Quiz",
        data={"correct_answer": "str", "options": [{"value": "str"}, {"value": "int"}]},
    )
    code = MissionTask.objects.create(
        mission=mission,
        order=2,
        task_type="code",
        title="Code",
        data={"expected_output": "ok"},
    )
    return mission, quiz, code


def _answer(api, task, value):
    response = api.post(
        f"/api/mission-tasks/{task.id}/submit/", {"answer": value}, format="json"
    )
    assert response.status_code == 200, response.content
    return response.json()


# ── help offer after repeated failures ──────────────────────────────────────


def test_quiz_offers_help_from_the_third_failure(course):
    _, quiz, _ = course
    student = _user("learner")
    api = _client(student)
    for _ in range(HELP_AFTER_FAILURES - 1):
        assert _answer(api, quiz, "int")["progress"]["help_offer"] is None

    third = _answer(api, quiz, "int")
    assert third["progress"]["help_offer"] == {
        "failures": HELP_AFTER_FAILURES,
        "threshold": HELP_AFTER_FAILURES,
    }
    fourth = _answer(api, quiz, "int")
    assert fourth["progress"]["help_offer"]["failures"] == HELP_AFTER_FAILURES + 1
    # the event marks the moment help was first offered, not every later miss
    offers = LearningEvent.objects.filter(event_type=LearningEvent.HELP_OFFERED)
    assert offers.count() == 1
    assert offers.get().task_id == quiz.id and offers.get().meta["failures"] == 3


def test_solving_the_step_withdraws_the_offer(course):
    _, quiz, _ = course
    api = _client(_user("learner"))
    for _ in range(HELP_AFTER_FAILURES):
        _answer(api, quiz, "int")
    solved = _answer(api, quiz, "str")
    assert solved["correct"] is True
    assert solved["progress"]["help_offer"] is None


def test_offer_survives_a_page_reload(course):
    mission, quiz, _ = course
    api = _client(_user("reloader"))
    for _ in range(HELP_AFTER_FAILURES):
        _answer(api, quiz, "int")
    rows = api.get("/api/task-progress/", {"mission": mission.id}).json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert rows[0]["help_offer"]["failures"] == HELP_AFTER_FAILURES


def test_code_runs_offer_help_too(course):
    _, _, code = course
    student = _user("coder")
    for n in range(1, HELP_AFTER_FAILURES + 1):
        verdict = finish_code_run(
            student, code, code="x", stdout="nope", stderr="", exit_code=0,
            duration=0.1, reasons=[],
        )
        expected = None if n < HELP_AFTER_FAILURES else HELP_AFTER_FAILURES
        offer = verdict["progress"]["help_offer"]
        assert (offer["failures"] if offer else None) == expected
    assert LearningEvent.objects.filter(event_type=LearningEvent.HELP_OFFERED).count() == 1


def test_sandbox_failures_never_trigger_help(course):
    _, _, code = course
    student = _user("unlucky")
    for _ in range(HELP_AFTER_FAILURES + 2):
        finish_code_run(
            student, code, code="x", stdout="", stderr="", exit_code=None,
            duration=0, reasons=[REASON_UNAVAILABLE],
        )
    assert not TaskProgress.objects.filter(user=student).exists()
    assert not LearningEvent.objects.filter(event_type=LearningEvent.HELP_OFFERED).exists()


# ── early warning ───────────────────────────────────────────────────────────


def _attempts(user, task, failures, *, when=None, solved=False):
    TaskProgress.objects.create(
        user=user,
        task=task,
        attempts=failures + (1 if solved else 0),
        status="completed" if solved else "in_progress",
        last_submitted_at=when or timezone.now(),
    )


def _open(user, mission, *, when=None):
    when = when or timezone.now()
    Progress.objects.create(
        user=user, mission=mission, status="in_progress", started_at=when, last_started_at=when
    )


def _warning(viewer):
    response = _client(viewer).get(WARNING_URL)
    assert response.status_code == 200, response.content
    return response.json()


def _levels(body):
    return {s["username"]: s["level"] for s in body["students"]}


def test_levels_follow_the_rules(teacher, course):
    mission, quiz, code = course
    old = timezone.now() - timedelta(days=10)
    cases = {
        "steady": lambda u: (_open(u, mission), _attempts(u, quiz, 1)),
        "stuck": lambda u: (_open(u, mission), _attempts(u, quiz, 3)),
        "deep": lambda u: (_open(u, mission), _attempts(u, code, 5)),
        "gone": lambda u: (_open(u, mission, when=old), _attempts(u, quiz, 1, when=old)),
        "gone_and_stuck": lambda u: (
            _open(u, mission, when=old),
            _attempts(u, quiz, 3, when=old),
        ),
        "recovered": lambda u: (_open(u, mission), _attempts(u, quiz, 4, solved=True)),
        "finished_long_ago": lambda u: Progress.objects.create(
            user=u, mission=mission, completed=True, status="completed",
            started_at=old, last_started_at=old, completed_at=old,
        ),
    }
    for name, build in cases.items():
        build(_user(name))

    body = _warning(teacher)
    assert _levels(body) == {
        "stuck": "medium",
        "deep": "high",
        "gone": "medium",
        "gone_and_stuck": "high",
    }
    assert body["summary"] == {"total": 7, "high": 2, "medium": 2}


def test_reasons_explain_the_flag(teacher, course):
    mission, quiz, _ = course
    old = timezone.now() - timedelta(days=9)
    student = _user("gone_and_stuck")
    _open(student, mission, when=old)
    _attempts(student, quiz, 4, when=old)

    entry = _warning(teacher)["students"][0]
    stuck = next(r for r in entry["reasons"] if r["code"] == "stuck_task")
    assert (stuck["failures"], stuck["task_id"], stuck["task_type"]) == (4, quiz.id, "quiz")
    assert stuck["task_title"] == "Quiz" and stuck["mission_title"] == "Basics"
    inactive = next(r for r in entry["reasons"] if r["code"] == "inactive")
    assert inactive["days"] >= 9
    assert entry["failures"] == 4


def test_a_few_quiet_days_alone_are_not_a_warning(teacher, course):
    mission, quiz, _ = course
    quiet = timezone.now() - timedelta(days=4)
    student = _user("quiet")
    _open(student, mission, when=quiet)
    _attempts(student, quiz, 1, when=quiet)
    assert _warning(teacher)["students"] == []


def test_most_urgent_first(teacher, course):
    mission, quiz, code = course
    medium, high = _user("a_medium"), _user("b_high")
    _open(medium, mission)
    _attempts(medium, quiz, 3)
    _open(high, mission)
    _attempts(high, code, 6)
    assert [s["username"] for s in _warning(teacher)["students"]] == ["b_high", "a_medium"]


def test_teachers_see_only_their_own_learners(teacher, course):
    mission, quiz, _ = course
    student = _user("mine")
    _open(student, mission)
    _attempts(student, quiz, 3)
    assert _levels(_warning(teacher)) == {"mine": "medium"}

    other = _user("other_teacher", is_staff=True)
    assert _warning(other)["students"] == []
    boss = _user("boss", is_staff=True, is_superuser=True)
    assert _levels(_warning(boss)) == {"mine": "medium"}


def test_staff_are_not_assessed(teacher, course):
    mission, quiz, _ = course
    colleague = _user("colleague", is_staff=True)
    _open(colleague, mission)
    _attempts(colleague, quiz, 5)
    assert _warning(teacher)["students"] == []


def test_early_warning_is_staff_only(course):
    assert APIClient().get(WARNING_URL).status_code == 401
    assert _client(_user("learner")).get(WARNING_URL).status_code == 403


def test_rules_are_published_with_the_list(teacher):
    rules = _warning(teacher)["rules"]
    assert rules["stuck_failures"] == HELP_AFTER_FAILURES
    assert rules["inactive_long_days"] == 7
