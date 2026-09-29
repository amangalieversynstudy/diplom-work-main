"""Learning-effectiveness metrics: MCR, MAS, drop-out, failure streaks, help effect."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.metrics import (
    CRITICAL_DROPOUT_SHARE,
    MIN_SAMPLE,
    _critical_threshold,
    clamp_inactive_days,
)
from game.models import (
    CodeRun,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)

User = get_user_model()

URL = "/api/analytics/metrics/"
EXPORT_URL = "/api/analytics/metrics/export/"


def _user(name, **extra):
    return User.objects.create_user(username=name, password="TestPass123!", **extra)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _course(owner, slug="course"):
    track = Track.objects.create(slug=slug, title=slug, owner=owner)
    location = Location.objects.create(track=track, title="Loc")
    mission = Mission.objects.create(location=location, title="Mission", xp_reward=10)
    story = MissionTask.objects.create(mission=mission, order=1, task_type="story")
    quiz = MissionTask.objects.create(mission=mission, order=2, task_type="quiz")
    code = MissionTask.objects.create(mission=mission, order=3, task_type="code")
    return track, mission, story, quiz, code


def _try(user, task, attempts, *, solved, when=None):
    """A learner's TaskProgress after ``attempts`` counted tries."""
    return TaskProgress.objects.create(
        user=user,
        task=task,
        attempts=attempts,
        status="completed" if solved else "in_progress",
        last_submitted_at=when or timezone.now(),
    )


def _mission_row(user, mission, *, completed):
    return Progress.objects.create(
        user=user,
        mission=mission,
        completed=completed,
        status="completed" if completed else "in_progress",
        started_at=timezone.now(),
        last_started_at=timezone.now(),
    )


@pytest.fixture
def teacher(db):
    return _user("teacher", is_staff=True)


@pytest.fixture
def class_room(teacher):
    """Four learners on one quiz step.

    A solves first try, B on the third try; C failed twice and left a month ago;
    D failed once and is still around.
    """
    _, mission, story, quiz, code = _course(teacher)
    a, b, c, d = (_user(name) for name in "abcd")
    old = timezone.now() - timedelta(days=30)
    _try(a, quiz, 1, solved=True)
    _try(b, quiz, 3, solved=True)
    _try(c, quiz, 2, solved=False, when=old)
    _try(d, quiz, 1, solved=False)
    _mission_row(a, mission, completed=True)
    _mission_row(b, mission, completed=True)
    _mission_row(c, mission, completed=False)
    _mission_row(d, mission, completed=False)
    Progress.objects.filter(user=c).update(last_started_at=old, started_at=old)
    return {"mission": mission, "quiz": quiz, "code": code, "users": (a, b, c, d)}


def _get(user, **params):
    response = _client(user).get(URL, params)
    assert response.status_code == 200, response.content
    return response.json()


def test_kpi_formulas(teacher, class_room):
    kpi = _get(teacher)["kpi"]
    assert kpi["mission_completion_rate"] == 50.0  # 2 of 4 started
    assert kpi["mean_attempts_to_success"] == 2.0  # (1 + 3) / 2, unsolved ignored
    assert kpi["steps_opened"] == 4
    assert kpi["steps_dropped"] == 1  # only C is both unsolved and gone
    assert kpi["task_dropout_rate"] == 25.0


def test_task_row_and_funnel(teacher, class_room):
    data = _get(teacher)
    row = next(r for r in data["tasks"] if r["task_id"] == class_room["quiz"].pk)
    assert (row["opened"], row["solved"], row["dropped"]) == (4, 2, 1)
    assert row["solve_rate"] == 50.0
    assert row["mas"] == 2.0
    quiz_step = next(f for f in data["funnel"] if f["task_type"] == "quiz")
    assert quiz_step["dropout_rate"] == 25.0
    story_step = next(f for f in data["funnel"] if f["task_type"] == "story")
    assert story_step["opened"] == 0 and story_step["mas"] is None


def test_active_learner_is_not_a_dropout_until_inactive_window_passes(
    teacher, class_room
):
    d = class_room["users"][3]
    assert _get(teacher)["kpi"]["steps_dropped"] == 1
    TaskProgress.objects.filter(user=d).update(
        last_submitted_at=timezone.now() - timedelta(days=10)
    )
    Progress.objects.filter(user=d).update(
        last_started_at=timezone.now() - timedelta(days=10)
    )
    assert _get(teacher)["kpi"]["steps_dropped"] == 2
    # a longer patience window turns them back into "still around"
    assert _get(teacher, inactive_days=14)["kpi"]["steps_dropped"] == 1


def test_failure_streak_curve(teacher, class_room):
    curve = {p["failures"]: p for p in _get(teacher)["failure_curve"]}
    # B (2 failures, solved), C (2, unsolved), D (1, unsolved) reach one failure
    assert curve[1]["reached"] == 3 and curve[1]["dropout_rate"] == 33.3
    assert curve[2]["reached"] == 2 and curve[2]["dropped"] == 1
    assert curve[2]["dropout_rate"] == 50.0
    assert curve[3]["reached"] == 0 and curve[3]["dropout_rate"] is None


def test_critical_threshold_needs_a_real_sample():
    def point(k, reached, rate):
        return {"failures": k, "reached": reached, "dropout_rate": rate}

    share = 100 * CRITICAL_DROPOUT_SHARE
    curve = [
        point(1, 40, 10.0),
        point(2, MIN_SAMPLE - 1, 100.0),  # too few pairs to trust
        point(3, MIN_SAMPLE, share),
        point(4, MIN_SAMPLE, 100.0),
    ]
    assert _critical_threshold(curve) == 3
    assert _critical_threshold([point(1, 40, 10.0), point(2, 20, 30.0)]) is None


def test_critical_threshold_found_in_api(teacher):
    _, mission, _, quiz, _ = _course(teacher)
    gone = timezone.now() - timedelta(days=40)
    for i in range(MIN_SAMPLE):
        _try(_user(f"quitter{i}"), quiz, 3, solved=False, when=gone)
    data = _get(teacher)
    assert data["critical_threshold"] == 1  # everyone who failed once left


def test_help_effect_groups(teacher, class_room):
    quiz = class_room["quiz"]
    a, b, c, d = class_room["users"]
    LearningEvent.objects.create(user=a, task=quiz, event_type=LearningEvent.HINT_USED)
    LearningEvent.objects.create(user=b, task=quiz, event_type=LearningEvent.HINT_USED)
    LearningEvent.objects.create(user=b, task=quiz, event_type=LearningEvent.AI_HINT_USED)
    groups = {g["group"]: g for g in _get(teacher)["help_effect"]}
    assert groups["hint"]["pairs"] == 1 and groups["hint"]["mas"] == 1.0
    assert groups["ai"]["pairs"] == 1 and groups["ai"]["mas"] == 3.0  # AI beats hint
    assert groups["none"]["pairs"] == 2 and groups["none"]["solve_rate"] == 0.0
    task = next(r for r in _get(teacher)["tasks"] if r["task_id"] == quiz.pk)
    assert task["help_rate"] == 50.0


def test_top_errors_and_task_top_error(teacher, class_room):
    code = class_room["code"]
    a, b, *_ = class_room["users"]
    for user, error in ((a, "NameError"), (b, "NameError"), (b, "SyntaxError")):
        CodeRun.objects.create(user=user, task=code, outcome="error", error_type=error)
    CodeRun.objects.create(user=a, task=code, outcome="runner_error")
    data = _get(teacher)
    assert data["top_errors"][0] == {"error_type": "NameError", "runs": 2, "learners": 2}
    assert {e["error_type"] for e in data["top_errors"]} == {"NameError", "SyntaxError"}
    row = next(r for r in data["tasks"] if r["task_id"] == code.pk)
    assert row["top_error"] == "NameError"


def test_code_runs_alone_count_as_opened(teacher):
    _, _, _, _, code = _course(teacher)
    CodeRun.objects.create(user=_user("solo"), task=code, outcome="error")
    row = next(r for r in _get(teacher)["tasks"] if r["task_id"] == code.pk)
    assert row["opened"] == 1


def test_teacher_sees_only_own_courses(teacher, class_room):
    other = _user("other", is_staff=True)
    assert _get(other)["kpi"]["steps_opened"] == 0
    assert _get(other)["tasks"] == []
    boss = _user("boss", is_staff=True, is_superuser=True)
    data = _get(boss)
    assert data["kpi"]["steps_opened"] == 4 and data["meta"]["scope"] == "all"


def test_track_filter(teacher, class_room):
    other_track, _, _, other_quiz, _ = _course(teacher, slug="second")
    _try(_user("late"), other_quiz, 1, solved=True)
    everything = _get(teacher)
    assert everything["kpi"]["steps_opened"] == 5
    only_second = _get(teacher, track=other_track.pk)
    assert only_second["kpi"]["steps_opened"] == 1
    assert _get(teacher, track="oops")["kpi"]["steps_opened"] == 5


def test_staff_accounts_are_not_learners(teacher, class_room):
    _try(_user("prof", is_staff=True), class_room["quiz"], 1, solved=True)
    assert _get(teacher)["kpi"]["steps_opened"] == 4


def test_empty_state_has_no_division_errors(teacher):
    data = _get(teacher)
    assert data["kpi"]["mission_completion_rate"] is None
    assert data["kpi"]["mean_attempts_to_success"] is None
    assert data["critical_threshold"] is None


def test_metrics_are_staff_only(class_room):
    assert APIClient().get(URL).status_code == 401
    student = class_room["users"][0]
    assert _client(student).get(URL).status_code == 403
    assert _client(student).get(EXPORT_URL).status_code == 403


def test_inactive_days_is_clamped():
    assert clamp_inactive_days("3") == 3
    assert clamp_inactive_days("0") == 1
    assert clamp_inactive_days("9999") == 60
    assert clamp_inactive_days("abc") == 7
    assert clamp_inactive_days(None) == 7


def test_csv_export(teacher, class_room):
    response = _client(teacher).get(EXPORT_URL)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    text = response.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("mission_id,mission_title,task_id")
    assert len(lines) == 1 + 3  # header + story, quiz, code


def test_csv_export_neutralises_formulas(teacher):
    _, mission, *_ = _course(teacher)
    Mission.objects.filter(pk=mission.pk).update(title="", title_ru="=HYPERLINK(1)")
    text = _client(teacher).get(EXPORT_URL).content.decode("utf-8-sig")
    assert "'=HYPERLINK(1)" in text
    assert ",=HYPERLINK" not in text
