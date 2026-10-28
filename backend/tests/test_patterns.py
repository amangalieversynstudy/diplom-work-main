"""Tests for learner behavioral pattern extraction and classification (Step B)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.metrics import compute_metrics
from game.models import CodeRun, Enrollment, LearningEvent, Location, Mission, MissionTask, Progress, TaskProgress, Track
from game.patterns import classify_behavioral_pattern, compute_behavioral_patterns, student_behavioral_pattern

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_classify_behavioral_pattern_categories():
    assert (
        classify_behavioral_pattern(
            attempted_steps=0,
            mean_attempts=None,
            help_rate=None,
            help_events=0,
            mean_pauses=None,
            mean_away_count=None,
            paste_after_away_total=0,
        )
        == "insufficient_data"
    )
    assert (
        classify_behavioral_pattern(
            attempted_steps=3,
            mean_attempts=1.2,
            help_rate=0.0,
            help_events=0,
            mean_pauses=0.5,
            mean_away_count=0.2,
            paste_after_away_total=0,
        )
        == "independent"
    )
    assert (
        classify_behavioral_pattern(
            attempted_steps=3,
            mean_attempts=1.5,
            help_rate=0.67,
            help_events=2,
            mean_pauses=0.5,
            mean_away_count=0.0,
            paste_after_away_total=0,
        )
        == "help_assisted"
    )
    assert (
        classify_behavioral_pattern(
            attempted_steps=3,
            mean_attempts=3.5,
            help_rate=0.0,
            help_events=0,
            mean_pauses=0.5,
            mean_away_count=0.0,
            paste_after_away_total=0,
        )
        == "trial_and_error"
    )
    assert (
        classify_behavioral_pattern(
            attempted_steps=2,
            mean_attempts=1.0,
            help_rate=0.0,
            help_events=0,
            mean_pauses=1.0,
            mean_away_count=2.5,
            paste_after_away_total=1,
        )
        == "fragmented"
    )


def test_cohort_and_student_behavioral_patterns_integration():
    teacher = User.objects.create_user("t_pat", "t_pat@example.com", "S3cure-pass-1", is_staff=True)
    track = Track.objects.create(slug="pat-track", title="Pattern Course", is_active=True, is_public=True, owner=teacher)
    loc = Location.objects.create(track=track, title="Loc", order=1)
    mission = Mission.objects.create(location=loc, title="M1", order=1)
    t1 = MissionTask.objects.create(mission=mission, order=1, task_type="code", title="C1")
    t2 = MissionTask.objects.create(mission=mission, order=2, task_type="quiz", title="Q1")

    u_ind = User.objects.create_user("u_ind", "u_ind@example.com", "S3cure-pass-1")
    u_help = User.objects.create_user("u_help", "u_help@example.com", "S3cure-pass-1")
    u_trial = User.objects.create_user("u_trial", "u_trial@example.com", "S3cure-pass-1")
    u_frag = User.objects.create_user("u_frag", "u_frag@example.com", "S3cure-pass-1")

    for u in (u_ind, u_help, u_trial, u_frag):
        Progress.objects.create(user=u, mission=mission, status="in_progress")

    # 1. Independent learner: 1 attempt each, no help, low away/pauses
    TaskProgress.objects.create(user=u_ind, task=t1, status="completed", attempts=1)
    TaskProgress.objects.create(user=u_ind, task=t2, status="completed", attempts=1)
    CodeRun.objects.create(
        user=u_ind,
        task=t1,
        passed=True,
        outcome="passed",
        provenance={"elapsed_ms": 60_000, "active_ms": 55_000, "pause_count": 0, "away_count": 0},
    )

    # 2. Help-assisted learner: uses hints and AI mentor
    TaskProgress.objects.create(user=u_help, task=t1, status="completed", attempts=2)
    LearningEvent.objects.create(user=u_help, task=t1, event_type=LearningEvent.HINT_USED)
    LearningEvent.objects.create(user=u_help, task=t1, event_type=LearningEvent.AI_MENTOR_USED)

    # 3. Trial-and-error learner: 4 attempts per step, no hints
    TaskProgress.objects.create(user=u_trial, task=t1, status="completed", attempts=4)
    TaskProgress.objects.create(user=u_trial, task=t2, status="in_progress", attempts=3)

    # 4. Fragmented learner: frequent tab switches and paste_after_away
    TaskProgress.objects.create(user=u_frag, task=t1, status="completed", attempts=1)
    CodeRun.objects.create(
        user=u_frag,
        task=t1,
        passed=True,
        outcome="passed",
        provenance={"elapsed_ms": 90_000, "active_ms": 30_000, "pause_count": 2, "away_count": 3, "paste_after_away": 1},
    )

    assert student_behavioral_pattern(u_ind, owner=teacher)["code"] == "independent"
    assert student_behavioral_pattern(u_help, owner=teacher)["code"] == "help_assisted"
    assert student_behavioral_pattern(u_trial, owner=teacher)["code"] == "trial_and_error"
    assert student_behavioral_pattern(u_frag, owner=teacher)["code"] == "fragmented"

    metrics = compute_metrics(teacher, track_id=track.id)
    bp = metrics["behavioral_patterns"]
    assert bp["total_learners"] == 4
    assert bp["classified_learners"] == 4
    by_code = {row["code"]: row for row in bp["profiles"]}
    assert by_code["independent"]["count"] == 1
    assert by_code["help_assisted"]["count"] == 1
    assert by_code["trial_and_error"]["count"] == 1
    assert by_code["fragmented"]["count"] == 1
    assert by_code["independent"]["mean_performance"] is not None

    client = APIClient()
    client.force_authenticate(teacher)
    res_list = client.get("/api/teacher/students/")
    assert res_list.status_code == 200
    patterns_map = {s["username"]: s["behavioral_pattern"] for s in res_list.json()["students"]}
    assert patterns_map["u_ind"] == "independent"
    assert patterns_map["u_help"] == "help_assisted"
    assert patterns_map["u_trial"] == "trial_and_error"
    assert patterns_map["u_frag"] == "fragmented"

    res_detail = client.get(f"/api/teacher/students/{u_frag.id}/learning/")
    assert res_detail.status_code == 200
    assert res_detail.json()["behavioral_pattern"]["code"] == "fragmented"
    assert res_detail.json()["behavioral_pattern"]["paste_after_away_total"] == 1
