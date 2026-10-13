"""Daily early-warning snapshots (the data for hypothesis H3) and the statistics they use."""

from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from game import scheduler, snapshots
from game.models import (
    EarlyWarningSnapshot,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)
from game.stats import clustered_share, effective_n, wilson_interval

User = get_user_model()

pytestmark = pytest.mark.django_db


def _user(name, *, consent=True, **extra):
    user = User.objects.create_user(username=name, password="TestPass123!", **extra)
    if consent:
        user.profile.set_research_consent(True)
        user.profile.save()
    return user


@pytest.fixture
def course():
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    mission = Mission.objects.create(location=Location.objects.create(track=track, title="Loc"), title="M")
    quiz = MissionTask.objects.create(
        mission=mission, order=1, task_type="quiz",
        data={"correct_answer": "a", "options": [{"value": "a"}, {"value": "b"}]},
    )
    return mission, quiz


def _stuck(user, mission, quiz, *, failures=5, when=None):
    """A learner with an open mission who failed ``quiz`` ``failures`` times in a row."""
    when = when or timezone.now()
    Progress.objects.create(
        user=user, mission=mission, status="in_progress", started_at=when, last_started_at=when
    )
    TaskProgress.objects.create(
        user=user, task=quiz, attempts=failures, status="in_progress", last_submitted_at=when
    )
    LearningEvent.objects.filter(user=user).update(created_at=when)


# ── the statistics ──────────────────────────────────────────────────────────


def test_wilson_interval_matches_a_hand_calculation():
    low, high = wilson_interval(4, 5)
    assert low == pytest.approx(0.376, abs=2e-3) and high == pytest.approx(0.964, abs=2e-3)
    assert wilson_interval(0, 0) is None
    assert wilson_interval(10, 10)[1] == pytest.approx(1.0)  # never above 100%


def test_effective_n_counts_a_learners_rows_as_one_observation():
    assert effective_n([1, 1, 1, 1]) == 4
    assert effective_n([4]) == 1
    assert effective_n({"a": 3, "b": 1}) == pytest.approx(16 / 10)


def test_clustering_widens_the_interval():
    independent = clustered_share(8, [1] * 10)  # ten learners, one row each
    clustered = clustered_share(8, [5, 5])  # the same ten rows from two learners
    assert independent["share"] == clustered["share"] == 0.8
    assert clustered["n_eff"] < independent["n_eff"]
    assert (clustered["ci_high"] - clustered["ci_low"]) > (independent["ci_high"] - independent["ci_low"])
    assert clustered_share(0, []) is None


# ── taking the snapshot ─────────────────────────────────────────────────────


def test_snapshot_stores_the_list_of_consenting_learners_only(course):
    mission, quiz = course
    stuck = _user("stuck")
    _stuck(stuck, mission, quiz)
    refuser = _user("refuser", consent=False)
    _stuck(refuser, mission, quiz)
    _user("teacher", is_staff=True)

    assert snapshots.take_snapshot() == 1
    row = EarlyWarningSnapshot.objects.get()
    assert row.user_id == stuck.pk and row.level == "high"
    assert row.reasons == ["stuck_task"]  # codes only: no step, no name
    assert row.date == timezone.now().astimezone(dt_timezone.utc).date()


def test_snapshot_is_idempotent_for_a_date(course):
    mission, quiz = course
    _stuck(_user("a"), mission, quiz)
    assert snapshots.take_snapshot() == 1
    _stuck(_user("late"), mission, quiz)  # appears later the same day
    assert snapshots.take_snapshot() == 0
    call_command("snapshot_early_warning", stdout=StringIO())
    assert EarlyWarningSnapshot.objects.count() == 1


def test_a_new_day_gets_its_own_snapshot(course):
    mission, quiz = course
    _stuck(_user("a"), mission, quiz)
    now = timezone.now()
    snapshots.take_snapshot(now=now)
    snapshots.take_snapshot(now=now + timedelta(days=1))
    assert EarlyWarningSnapshot.objects.count() == 2


def test_a_learner_who_never_did_anything_is_not_stored():
    _user("idle")
    assert snapshots.take_snapshot() == 0


def test_the_scheduler_runs_the_snapshot_and_survives_a_failing_job():
    called = []

    def fake(name):
        called.append(name)
        if name == "send_streak_reminders":
            raise RuntimeError("mail is down")

    with patch("django.core.management.call_command", side_effect=fake):
        scheduler._run_once()
    assert called == ["send_streak_reminders", "snapshot_early_warning"]


# ── H3 ──────────────────────────────────────────────────────────────────────


def _snapshot_row(user, day, level):
    return EarlyWarningSnapshot.objects.create(date=day, user=user, level=level, score=4 if level == "high" else 0)


def test_h3_compares_leavers_among_urgent_and_the_rest():
    now = timezone.now()
    day = (now - timedelta(days=20)).astimezone(dt_timezone.utc).date()
    after = datetime.combine(day + timedelta(days=2), datetime.min.time(), tzinfo=dt_timezone.utc)
    urgent_gone = [_user(f"ug{i}") for i in range(3)]
    urgent_stay = _user("us")
    others_stay = [_user(f"os{i}") for i in range(4)]
    for user in urgent_gone:
        _snapshot_row(user, day, "high")
    _snapshot_row(urgent_stay, day, "high")
    for user in others_stay:
        _snapshot_row(user, day, "ok")
    for user in [urgent_stay, *others_stay]:  # came back inside the window
        LearningEvent.objects.create(user=user, event_type="login")
        LearningEvent.objects.filter(user=user).update(created_at=after)

    result = snapshots.h3_summary(now=now)
    assert result["mature_days"] == 1
    assert result["levels"]["high"]["rows"] == 4 and result["levels"]["high"]["left"] == 3
    assert result["levels"]["high"]["share"] == 75.0
    assert result["levels"]["ok"]["left"] == 0 and result["levels"]["ok"]["share"] == 0.0
    assert result["levels"]["high"]["ci_low"] < 75.0 < result["levels"]["high"]["ci_high"]
    assert result["recall_listed"] == 100.0  # every leaver had been on the list
    assert result["levels"]["medium"]["rows"] == 0 and result["levels"]["medium"]["share"] is None


def test_h3_ignores_snapshots_whose_window_is_not_over_yet():
    now = timezone.now()
    young = (now - timedelta(days=10)).astimezone(dt_timezone.utc).date()
    _snapshot_row(_user("fresh"), young, "high")
    result = snapshots.h3_summary(now=now)
    assert result["mature_days"] == 0 and result["all"]["rows"] == 0


def test_h3_ignores_learners_who_withdrew_consent():
    now = timezone.now()
    day = (now - timedelta(days=20)).astimezone(dt_timezone.utc).date()
    withdrawn = _user("withdrawn")
    _snapshot_row(withdrawn, day, "high")
    withdrawn.profile.set_research_consent(False)
    withdrawn.profile.save()
    assert snapshots.h3_summary(now=now)["all"]["rows"] == 0
