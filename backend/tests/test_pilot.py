"""Pilot tooling: the help experiment, the weekly report, readiness and ownership."""

import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from game import pilot
from game.management.commands import pilot_check
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
from game.services import ARM_CONTROL, ARM_OFFER, HELP_AFTER_FAILURES, help_arm

User = get_user_model()

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"


def _user(name, **extra):
    return User.objects.create_user(username=name, password=PASSWORD, **extra)


@pytest.fixture
def course():
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    mission = Mission.objects.create(
        location=Location.objects.create(track=track, title="Loc"), title="M"
    )
    quiz = MissionTask.objects.create(
        mission=mission, order=1, task_type="quiz",
        data={"correct_answer": "a", "options": [{"value": "a"}, {"value": "b"}]},
    )
    return track, mission, quiz


def _in_arm(arm, prefix="l"):
    """A fresh learner who the current HELP_OFFER_SHARE puts into ``arm``."""
    for number in range(1000):
        user = _user(f"{prefix}{arm}{number}")
        if help_arm(user.pk) == arm:
            return user
    raise AssertionError("no learner landed in the arm")


# ── randomised help prompt ──────────────────────────────────────────────────


def test_everyone_sees_the_prompt_by_default(settings):
    settings.HELP_OFFER_SHARE = 100
    assert {help_arm(n) for n in range(200)} == {ARM_OFFER}


def test_zero_share_means_nobody_and_out_of_range_is_clamped(settings):
    settings.HELP_OFFER_SHARE = 0
    assert {help_arm(n) for n in range(200)} == {ARM_CONTROL}
    settings.HELP_OFFER_SHARE = 500
    assert {help_arm(n) for n in range(50)} == {ARM_OFFER}


def test_half_share_splits_learners_stably_and_evenly(settings):
    settings.HELP_OFFER_SHARE = 50
    arms = [help_arm(n) for n in range(2000)]
    assert arms == [help_arm(n) for n in range(2000)]  # the same learner, the same arm
    offered = arms.count(ARM_OFFER) / len(arms)
    assert 0.45 < offered < 0.55


def _fail_quiz(user, quiz, times):
    api = APIClient()
    api.force_authenticate(user)
    last = None
    for _ in range(times):
        last = api.post(
            f"/api/mission-tasks/{quiz.id}/submit/", {"answer": "b"}, format="json"
        ).json()
    return last


def test_control_learners_get_no_banner_but_the_moment_is_recorded(settings, course):
    settings.HELP_OFFER_SHARE = 50
    _, _, quiz = course
    seen, unseen = _in_arm(ARM_OFFER), _in_arm(ARM_CONTROL)

    assert _fail_quiz(seen, quiz, HELP_AFTER_FAILURES)["progress"]["help_offer"] is not None
    assert _fail_quiz(unseen, quiz, HELP_AFTER_FAILURES)["progress"]["help_offer"] is None

    events = {
        e.user_id: e.meta
        for e in LearningEvent.objects.filter(event_type=LearningEvent.HELP_OFFERED)
    }
    assert events[seen.pk]["arm"] == ARM_OFFER and events[seen.pk]["shown"] is True
    assert events[unseen.pk]["arm"] == ARM_CONTROL and events[unseen.pk]["shown"] is False


# ── the arithmetic ──────────────────────────────────────────────────────────


def test_two_proportions_matches_a_hand_calculation():
    result = pilot.two_proportions(30, 100, 20, 100)
    assert result["diff"] == pytest.approx(0.10)
    assert result["ci_low"] == pytest.approx(-0.0192, abs=1e-3)
    assert result["ci_high"] == pytest.approx(0.2192, abs=1e-3)
    assert result["p_value"] == pytest.approx(0.1025, abs=1e-3)


def test_two_proportions_edge_cases():
    assert pilot.two_proportions(1, 0, 1, 5) is None
    same = pilot.two_proportions(10, 50, 10, 50)
    assert same["diff"] == 0 and same["p_value"] == pytest.approx(1.0)
    assert pilot.two_proportions(0, 20, 0, 20)["p_value"] == pytest.approx(1.0)  # no variance


# ── the report ──────────────────────────────────────────────────────────────


def _offered(user, task, arm, *, solved, attempts, gone=False):
    event = LearningEvent.objects.create(
        user=user, task=task, event_type=LearningEvent.HELP_OFFERED,
        meta={"arm": arm, "shown": arm == ARM_OFFER, "failures": 3},
    )
    TaskProgress.objects.create(
        user=user, task=task, attempts=attempts,
        status="completed" if solved else "in_progress",
        last_submitted_at=timezone.now(),
    )
    if gone:
        old = timezone.now() - timedelta(days=30)
        LearningEvent.objects.filter(user=user).update(created_at=old)
        TaskProgress.objects.filter(user=user).update(last_submitted_at=old)
    return event


def test_report_on_an_empty_platform_does_not_break():
    report = pilot.build_report()
    text = pilot.render_markdown(report)
    assert report["participants"]["learners"] == 0
    assert "Пока никто не дошёл до порога" in text and "Запусков кода пока нет" in text


def test_report_counts_participants_and_consent(course):
    _, mission, quiz = course
    yes, no = _user("yes"), _user("no")
    _user("idle")
    _user("teacher", is_staff=True)
    yes.profile.set_research_consent(True)
    yes.profile.save()
    for user in (yes, no):
        LearningEvent.objects.create(user=user, event_type="task_opened", task=quiz)
    Progress.objects.create(
        user=yes, mission=mission, completed=True, status="completed",
        started_at=timezone.now(), completed_at=timezone.now(),
    )
    p = pilot.build_report()["participants"]
    assert (p["learners"], p["consented"], p["with_activity"]) == (3, 1, 2)
    assert (p["started_a_mission"], p["finished_a_mission"]) == (1, 1)
    assert p["activity_without_consent"] == 1
    assert p["active_by_week"][-1] == 2  # both were active this week


def test_help_experiment_compares_the_arms(course):
    _, _, quiz = course
    for i in range(3):  # prompt shown: all solve
        _offered(_user(f"o{i}"), quiz, ARM_OFFER, solved=True, attempts=4)
    for i in range(2):  # control: one solves, one leaves for good
        _offered(_user(f"c{i}"), quiz, ARM_CONTROL, solved=i == 0, attempts=5 if i == 0 else 3, gone=i == 1)
    HINT = LearningEvent.HINT_USED
    LearningEvent.objects.create(user=User.objects.get(username="o0"), task=quiz, event_type=HINT)

    result = pilot.help_experiment(timezone.now())
    offer, control = result["arms"][ARM_OFFER], result["arms"][ARM_CONTROL]
    assert (offer["pairs"], offer["solved"], offer["dropped"]) == (3, 3, 0)
    assert offer["extra_attempts"] == 1.0  # solved on attempt 4 after the 3 failures
    assert offer["helped_after_rate"] == pytest.approx(33.3, abs=0.1)
    assert (control["pairs"], control["solved"], control["dropped"]) == (2, 1, 1)
    assert control["extra_attempts"] == 2.0
    assert result["comparison"]["enough"] is False  # far below 30 pairs


def test_events_without_an_arm_are_assigned_the_learners_arm(course):
    _, _, quiz = course
    user = _user("old")
    LearningEvent.objects.create(
        user=user, task=quiz, event_type=LearningEvent.HELP_OFFERED, meta={"failures": 3}
    )
    assert set(pilot.help_experiment(timezone.now())["arms"]) == {help_arm(user.pk)}


def test_sandbox_health_flags_unreliable_runs(course):
    _, _, quiz = course
    user = _user("runner")
    for outcome in ["success"] * 8 + ["runner_error"] * 2:
        CodeRun.objects.create(user=user, task=None, outcome=outcome, duration_ms=100)
    health = pilot.sandbox_health()
    assert health["runner_error_rate"] == 20.0 and health["median_ms"] == 100
    assert "Сбоев больше 2%" in pilot.render_markdown(pilot.build_report())


def test_report_command_writes_markdown_and_json(tmp_path, course):
    out = tmp_path / "sub" / "report.md"
    call_command("pilot_report", "--out", str(out), stdout=StringIO())
    assert "# Отчёт пилота" in out.read_text(encoding="utf-8")

    buffer = StringIO()
    call_command("pilot_report", "--json", stdout=buffer)
    assert json.loads(buffer.getvalue())["participants"]["learners"] == 0


# ── course owner ────────────────────────────────────────────────────────────


def test_set_course_owner_gives_the_teacher_the_course(course):
    track, _, _ = course
    teacher = _user("teacher", is_staff=True)
    call_command("set_course_owner", "py", "teacher", stdout=StringIO())
    track.refresh_from_db()
    assert track.owner_id == teacher.pk


@pytest.mark.parametrize(
    "args", [("py", "learner"), ("py", "ghost"), ("nope", "teacher")]
)
def test_set_course_owner_refuses_bad_input(course, args):
    _user("teacher", is_staff=True)
    _user("learner")
    with pytest.raises(CommandError):
        call_command("set_course_owner", *args, stdout=StringIO())
    assert Track.objects.get(slug="py").owner_id is None


# ── readiness ───────────────────────────────────────────────────────────────


def _levels(**overrides):
    return {
        message: level
        for level, message in (*pilot_check.check_settings(), *pilot_check.check_data())
    }


@pytest.fixture
def ready(settings, course):
    """A configuration that passes: teacher owns the course, sandbox reachable."""
    track, _, _ = course
    teacher = _user("teacher", is_staff=True)
    Track.objects.update(owner=teacher)  # migrations seed another track too
    settings.DEBUG = False
    settings.SECRET_KEY = "k" * 60
    settings.RUNNER_ALLOW_UNSAFE_FALLBACK = False
    settings.HELP_OFFER_SHARE = 50
    with patch.object(pilot_check, "docker_reachable", return_value=True):
        yield settings


def _run_check():
    out = StringIO()
    call_command("pilot_check", stdout=out)
    return out.getvalue()


def test_a_ready_deployment_passes(ready):
    assert "Проверка пройдена" in _run_check()


@pytest.mark.parametrize(
    "setting, value, fragment",
    [
        ("DEBUG", True, "DEBUG включён"),
        ("SECRET_KEY", "short", "SECRET_KEY короткий"),
        ("RUNNER_ALLOW_UNSAFE_FALLBACK", True, "выполнялся бы на сервере"),
    ],
)
def test_dangerous_settings_fail_the_check(ready, setting, value, fragment):
    setattr(ready, setting, value)
    with pytest.raises(CommandError):
        out = StringIO()
        try:
            call_command("pilot_check", stdout=out)
        finally:
            assert fragment in out.getvalue()


def test_no_sandbox_fails_and_public_judge0_warns(ready):
    with patch.object(pilot_check, "docker_reachable", return_value=False):
        with pytest.raises(CommandError):
            call_command("pilot_check", stdout=StringIO())
        ready.RUNNER_JUDGE0_URL = "https://ce.judge0.com"
        output = _run_check()
    assert "ce.judge0.com" in output and "WARN" in output


def test_a_course_without_an_owner_warns_when_a_superuser_exists(ready):
    Track.objects.update(owner=None)
    _user("boss", is_staff=True, is_superuser=True)
    output = _run_check()
    assert "set_course_owner" in output


def test_control_group_is_flagged_when_missing(ready):
    ready.HELP_OFFER_SHARE = 100
    assert "контрольной группы нет" in _run_check()


def test_missing_course_or_teacher_fails(ready):
    Track.objects.all().delete()
    with pytest.raises(CommandError):
        call_command("pilot_check", stdout=StringIO())
