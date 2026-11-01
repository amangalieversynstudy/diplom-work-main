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


def _snapshot_row(user, day, level, reasons=None):
    return EarlyWarningSnapshot.objects.create(
        date=day, user=user, level=level, score=4 if level == "high" else 0, reasons=reasons or []
    )


def _event(user, when):
    """One sign of life of ``user`` at ``when``."""
    event = LearningEvent.objects.create(user=user, event_type="login")
    LearningEvent.objects.filter(pk=event.pk).update(created_at=when)


def _midday(day):
    return datetime.combine(day, datetime.min.time(), tzinfo=dt_timezone.utc) + timedelta(hours=12)


def _learning(user, mission, day):
    """``user`` is inside an unfinished course on ``day`` and was active the day before: a real forecast row."""
    Progress.objects.create(
        user=user, mission=mission, status="in_progress", started_at=_midday(day - timedelta(days=5))
    )
    _event(user, _midday(day - timedelta(days=1)))


@pytest.fixture
def h3_day():
    return (timezone.now() - timedelta(days=20)).astimezone(dt_timezone.utc).date()


def test_h3_compares_leavers_among_urgent_and_the_rest(course, h3_day):
    mission, _ = course
    day = h3_day
    urgent_gone = [_user(f"ug{i}") for i in range(3)]
    urgent_stay = _user("us")
    others_stay = [_user(f"os{i}") for i in range(4)]
    for user in [*urgent_gone, urgent_stay, *others_stay]:
        _learning(user, mission, day)
    for user in urgent_gone:
        _snapshot_row(user, day, "high", ["stuck_task"])
    _snapshot_row(urgent_stay, day, "high", ["stuck_task"])
    for user in others_stay:
        _snapshot_row(user, day, "ok")
    for user in [urgent_stay, *others_stay]:  # came back inside the window
        _event(user, _midday(day + timedelta(days=2)))

    result = snapshots.h3_summary(now=timezone.now())
    assert result["mature_days"] == 1
    assert result["levels"]["high"]["rows"] == 4 and result["levels"]["high"]["left"] == 3
    assert result["levels"]["high"]["share"] == 75.0
    assert result["levels"]["ok"]["left"] == 0 and result["levels"]["ok"]["share"] == 0.0
    assert result["levels"]["high"]["ci_low"] < 75.0 < result["levels"]["high"]["ci_high"]
    assert result["recall_listed"] == 100.0  # every leaver had been on the list
    assert result["recall_learners"] == {"left": 3, "flagged_before": 3, "share": 100.0}
    assert result["levels"]["medium"]["rows"] == 0 and result["levels"]["medium"]["share"] is None
    assert result["by_reason"]["stuck"]["rows"] == 4 and result["by_reason"]["inactive"]["rows"] == 0
    main = result["difference_high_ok"]
    assert main["estimate"] == 75.0 and main["learners_a"] == 4 and main["learners_b"] == 4
    assert main["replicates"] >= 100 and main["ci_low"] <= 75.0 <= main["ci_high"]
    assert result["excluded"] == {"after_end": 0, "not_in_course": 0, "already_gone": 0, "after_contact": 0}


def test_h3_ignores_snapshots_whose_window_is_not_over_yet(course):
    mission, _ = course
    young = (timezone.now() - timedelta(days=10)).astimezone(dt_timezone.utc).date()
    fresh = _user("fresh")
    _learning(fresh, mission, young)
    _snapshot_row(fresh, young, "high")
    result = snapshots.h3_summary(now=timezone.now())
    assert result["mature_days"] == 0 and result["all"]["rows"] == 0


def test_h3_ignores_learners_who_withdrew_consent(course, h3_day):
    mission, _ = course
    withdrawn = _user("withdrawn")
    _learning(withdrawn, mission, h3_day)
    _snapshot_row(withdrawn, h3_day, "high")
    withdrawn.profile.set_research_consent(False)
    withdrawn.profile.save()
    assert snapshots.h3_summary(now=timezone.now())["all"]["rows"] == 0


def test_h3_a_finished_course_is_censored_not_left(course, h3_day):
    """Silence after finishing the course is not leaving: the row is left out, not counted as a leaver."""
    mission, _ = course
    done = _user("done")
    Progress.objects.create(
        user=done, mission=mission, status="completed", completed=True,
        started_at=_midday(h3_day - timedelta(days=6)), completed_at=_midday(h3_day - timedelta(days=1)),
    )
    _event(done, _midday(h3_day - timedelta(days=1)))
    _snapshot_row(done, h3_day, "ok")
    result = snapshots.h3_summary(now=timezone.now())
    assert result["all"]["rows"] == 0 and result["excluded"]["not_in_course"] == 1


def test_h3_a_learner_already_gone_is_not_a_forecast(course, h3_day):
    """Silent for the whole window before the snapshot: the list would only "predict" that the silent stay silent."""
    mission, _ = course
    ghost = _user("ghost")
    Progress.objects.create(
        user=ghost, mission=mission, status="in_progress", started_at=_midday(h3_day - timedelta(days=30))
    )
    _event(ghost, _midday(h3_day - timedelta(days=20)))
    _snapshot_row(ghost, h3_day, "medium", ["inactive"])
    result = snapshots.h3_summary(now=timezone.now())
    assert result["all"]["rows"] == 0 and result["excluded"]["already_gone"] == 1


def test_h3_windows_past_the_end_of_the_pilot_are_censored(course, h3_day, settings):
    mission, _ = course
    quiet = _user("quiet")
    _learning(quiet, mission, h3_day)
    _snapshot_row(quiet, h3_day, "high")
    # the course ended a week after the snapshot: the 14-day window runs past it
    settings.PILOT_ENDED_AT = (_midday(h3_day + timedelta(days=7))).isoformat()
    result = snapshots.h3_summary(now=timezone.now())
    assert result["all"]["rows"] == 0 and result["excluded"]["after_end"] == 1
    settings.PILOT_ENDED_AT = (_midday(h3_day + timedelta(days=16))).isoformat()
    assert snapshots.h3_summary(now=timezone.now())["all"]["rows"] == 1


def test_h3_takes_only_learners_who_signed_up_since_the_start(course, h3_day, settings):
    """Rehearsal accounts made before PILOT_STARTED_AT drop out by themselves."""
    mission, _ = course
    rehearsal, pilot = _user("rehearsal"), _user("pilot")
    for user in (rehearsal, pilot):
        _learning(user, mission, h3_day)
        _snapshot_row(user, h3_day, "high")
    start = _midday(h3_day - timedelta(days=10))
    User.objects.filter(pk=rehearsal.pk).update(date_joined=start - timedelta(days=3))
    User.objects.filter(pk=pilot.pk).update(date_joined=start + timedelta(hours=1))
    settings.PILOT_STARTED_AT = start.isoformat()
    result = snapshots.h3_summary(now=timezone.now())
    assert result["all"]["rows"] == 1 and result["levels"]["high"]["learners"] == 1


def test_h3_days_after_the_teachers_contact_are_left_out(course, h3_day):
    mission, _ = course
    helped = _user("helped")
    _learning(helped, mission, h3_day)
    _snapshot_row(helped, h3_day, "high")
    _snapshot_row(helped, h3_day - timedelta(days=1), "high")
    result = snapshots.h3_summary(now=timezone.now(), contacts={helped.pk: h3_day})
    assert result["all"]["rows"] == 1 and result["excluded"]["after_contact"] == 1 and result["contacts"] == 1


def test_bootstrap_difference_is_deterministic_and_resamples_learners():
    rows = {(user, day): level for user, level in ((1, "high"), (2, "high"), (3, "ok"), (4, "ok")) for day in (1, 2)}
    left = {(1, 1), (1, 2), (2, 1)}
    first = snapshots.bootstrap_difference(rows, left, {"high"}, {"ok"}, seed=3)
    again = snapshots.bootstrap_difference(rows, left, {"high"}, {"ok"}, seed=3)
    assert first == again
    assert first["estimate"] == 75.0 and first["learners_a"] == 2 and first["learners_b"] == 2
    # with two learners per group a learner-level resample can draw only "ok" learners: those replicates are skipped
    assert first["replicates"] < 2000 and first["ci_low"] <= 75.0 <= first["ci_high"]
    assert snapshots.bootstrap_difference({}, set(), {"high"}, {"ok"})["estimate"] is None


def test_no_snapshot_after_the_end_of_the_pilot(course, settings):
    mission, quiz = course
    _stuck(_user("late"), mission, quiz)
    settings.PILOT_ENDED_AT = (timezone.now() - timedelta(hours=1)).isoformat()
    assert snapshots.take_snapshot() == 0 and not EarlyWarningSnapshot.objects.exists()
