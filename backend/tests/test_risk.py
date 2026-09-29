"""Risk model on the platform: features, JSON scoring, early-warning signal, export."""

import csv
import importlib.util
import json
import math
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from game import risk
from game.models import (
    CodeRun,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    Track,
)
from game.risk import RiskModel, features_from, load_risk_model

User = get_user_model()

pytestmark = pytest.mark.django_db

ML_SCHEMA = Path(__file__).resolve().parents[2] / "ml" / "risk" / "schema.py"


def model_data(**overrides):
    """A tiny model: more activity means less risk."""
    data = {
        "schema_version": 1,
        "kind": "logistic",
        "source": "platform",
        "features": list(risk.FEATURES),
        "mean": [3.0, 20.0, 8.0, 0.4, 2.0, 0.3],
        "scale": [2.0, 15.0, 6.0, 0.3, 2.0, 0.3],
        "coef": [-0.5, -1.5, -0.3, -0.2, 0.0, 0.4],
        "intercept": -0.2,
        "threshold": 0.5,
        "window_days": 14,
        "horizon_days": 14,
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _fresh_model_cache():
    risk._loaded.update(key=None, model=None)
    yield
    risk._loaded.update(key=None, model=None)


def _user(name, **extra):
    return User.objects.create_user(username=name, password="TestPass123!", **extra)


def _back_date(model, pk, when):
    model.objects.filter(pk=pk).update(created_at=when)


# ── the contract with ml/ ───────────────────────────────────────────────────


def test_feature_contract_matches_the_ml_package():
    spec = importlib.util.spec_from_file_location("ml_schema", ML_SCHEMA)
    schema = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(schema)
    assert risk.FEATURES == schema.FEATURES
    assert risk.BASE_FEATURES == schema.BASE_FEATURES
    assert risk.SCHEMA_VERSION == schema.SCHEMA_VERSION


# ── scoring ─────────────────────────────────────────────────────────────────


def test_probability_is_the_logistic_of_standardised_features():
    model = RiskModel(model_data())
    features = {
        "active_days": 5, "events": 35, "events_last_week": 14, "recent_share": 0.4,
        "graded_attempted": 4, "graded_failed_share": 0.6,
    }
    z = -0.2
    for name, mean, scale, coef in zip(
        risk.FEATURES, model.mean, model.scale, model.coef
    ):
        z += coef * (features[name] - mean) / scale
    assert model.probability(features) == pytest.approx(1 / (1 + math.exp(-z)))


def test_probability_is_stable_for_extreme_inputs():
    model = RiskModel(model_data(coef=[-50.0] * 6))
    huge = {name: 1e6 for name in risk.FEATURES}
    tiny = {name: -1e6 for name in risk.FEATURES}
    assert model.probability(huge) == pytest.approx(0.0)
    assert model.probability(tiny) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"kind": "forest"},
        {"source": "OULAD"},  # trained to predict another outcome
        {"features": ["events"]},
        {"scale": [1, 1, 1, 1, 1]},
        {"scale": [0, 1, 1, 1, 1, 1]},
        {"window_days": 0},
    ],
)
def test_bad_model_files_are_rejected(change):
    with pytest.raises(ValueError):
        RiskModel(model_data(**change))


# ── loading ─────────────────────────────────────────────────────────────────


def test_no_model_configured_means_none(settings):
    settings.RISK_MODEL_PATH = ""
    assert load_risk_model() is None


def test_valid_file_is_loaded_and_picked_up_when_it_changes(settings, tmp_path):
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model_data(threshold=0.5)), encoding="utf-8")
    settings.RISK_MODEL_PATH = str(path)
    first = load_risk_model()
    assert first.threshold == 0.5 and load_risk_model() is first  # cached

    path.write_text(json.dumps(model_data(threshold=0.8)), encoding="utf-8")
    later = timezone.now().timestamp() + 5
    import os
    os.utime(path, (later, later))
    assert load_risk_model().threshold == 0.8


@pytest.mark.parametrize("content", [None, "not json", json.dumps(model_data(source="OULAD"))])
def test_unusable_model_never_breaks_anything(settings, tmp_path, content):
    path = tmp_path / "model.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    settings.RISK_MODEL_PATH = str(path)
    assert load_risk_model() is None


# ── features from the footprint ─────────────────────────────────────────────


@pytest.fixture
def quiz_and_code():
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    mission = Mission.objects.create(
        location=Location.objects.create(track=track, title="Loc"), title="M"
    )
    quiz = MissionTask.objects.create(mission=mission, order=1, task_type="quiz")
    code = MissionTask.objects.create(mission=mission, order=2, task_type="code")
    return mission, quiz, code


def test_activity_rows_count_graded_attempts_once(quiz_and_code):
    _, quiz, code = quiz_and_code
    learner = _user("learner")
    LearningEvent.objects.create(user=learner, event_type="login")
    LearningEvent.objects.create(
        user=learner, event_type="task_submitted", task=quiz,
        meta={"task_type": "quiz", "correct": False, "after_solved": False},
    )
    LearningEvent.objects.create(  # re-answering a solved quiz is not an attempt
        user=learner, event_type="task_submitted", task=quiz,
        meta={"task_type": "quiz", "correct": True, "after_solved": True},
    )
    LearningEvent.objects.create(  # story steps are never graded
        user=learner, event_type="task_submitted", meta={"task_type": "story", "correct": True},
    )
    CodeRun.objects.create(user=learner, task=code, outcome="wrong_output", passed=False)
    CodeRun.objects.create(user=learner, task=code, outcome="success", passed=True)
    CodeRun.objects.create(user=learner, task=None, outcome="success")  # free practice
    CodeRun.objects.create(user=learner, task=code, outcome="success", passed=True, after_solved=True)

    now = timezone.now() + timedelta(seconds=1)
    features = features_from(risk.activity_rows([learner.id])[learner.id], now, 14)
    assert features["events"] == 8
    assert features["graded_attempted"] == 3  # wrong quiz, failed run, passed run
    assert features["graded_failed"] == 2
    assert features["graded_failed_share"] == pytest.approx(2 / 3)
    assert features["active_days"] == 1


def test_window_features_ignore_old_activity_and_split_the_last_week():
    now = timezone.now()
    rows = [
        (now - timedelta(days=1), False, False),
        (now - timedelta(days=2), True, True),
        (now - timedelta(days=10), False, False),
        (now - timedelta(days=20), True, False),  # outside a 14-day window
    ]
    features = features_from(rows, now, 14)
    assert features["events"] == 3
    assert features["events_last_week"] == 2
    assert features["recent_share"] == pytest.approx(2 / 3)
    assert features["active_days"] == 3
    assert features_from([], now, 14)["recent_share"] == 0.0


# ── early warning ───────────────────────────────────────────────────────────


@pytest.fixture
def class_with_model(settings, tmp_path, quiz_and_code):
    teacher = _user("teacher", is_staff=True)
    mission, quiz, _ = quiz_and_code
    Track.objects.filter(pk=mission.location.track_id).update(owner=teacher)
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model_data()), encoding="utf-8")
    settings.RISK_MODEL_PATH = str(path)

    def learner(name, *, events, open_work=True):
        user = _user(name)
        if open_work:
            Progress.objects.create(
                user=user, mission=mission, status="in_progress",
                started_at=timezone.now(), last_started_at=timezone.now(),
            )
        for _ in range(events):
            LearningEvent.objects.create(user=user, event_type="task_opened", task=quiz)
        return user

    return teacher, learner


def _warning(teacher):
    client = APIClient()
    client.force_authenticate(teacher)
    response = client.get("/api/analytics/early-warning/")
    assert response.status_code == 200
    return response.json()


def test_model_flags_a_fading_learner_and_explains_it(class_with_model):
    teacher, learner = class_with_model
    learner("busy", events=60)
    learner("fading", events=0)

    body = _warning(teacher)
    assert body["rules"]["model"] is True
    flagged = {s["username"]: s for s in body["students"]}
    assert set(flagged) == {"fading"}
    reason = flagged["fading"]["reasons"][0]
    assert reason["code"] == "model_risk" and reason["probability"] >= 0.5
    assert flagged["fading"]["level"] == "medium"
    assert flagged["fading"]["risk_probability"] >= 0.5


def test_finished_learners_are_not_flagged_by_the_model(class_with_model):
    teacher, learner = class_with_model
    learner("done", events=0, open_work=False)
    assert _warning(teacher)["students"] == []


def test_without_a_model_the_list_works_from_rules_alone(settings, class_with_model):
    teacher, learner = class_with_model
    learner("fading", events=0)
    settings.RISK_MODEL_PATH = ""
    body = _warning(teacher)
    assert body["students"] == [] and body["rules"]["model"] is False


# ── export ──────────────────────────────────────────────────────────────────


def _timeline(user, days_ago):
    now = timezone.now()
    for day in days_ago:
        event = LearningEvent.objects.create(user=user, event_type="task_opened")
        _back_date(LearningEvent, event.pk, now - timedelta(days=day))


def _open_mission(user, mission, days_ago=40):
    Progress.objects.create(
        user=user, mission=mission, status="in_progress",
        started_at=timezone.now() - timedelta(days=days_ago),
    )


def _export(tmp_path, *extra):
    out = tmp_path / "features.csv"
    call_command("export_risk_features", "--out", str(out), *extra)
    with out.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _consenting(name):
    user = _user(name)
    user.profile.set_research_consent(True)
    user.profile.save()
    return user


def test_export_labels_dropouts_and_returners(tmp_path, quiz_and_code):
    mission = quiz_and_code[0]
    gone, back = _consenting("gone"), _consenting("back")
    for user, timeline in ((gone, [40, 38, 35]), (back, [40, 38, 35, 15])):
        _timeline(user, timeline)
        _open_mission(user, mission)

    by_learner = {}
    for row in _export(tmp_path):
        by_learner.setdefault(row["learner"], []).append(row)
    assert len(by_learner) == 2
    # first snapshot (26 days ago) sees the 3 early events; only one learner returns
    labels = sorted(int(rows[0]["label"]) for rows in by_learner.values())
    assert labels == [0, 1]
    row = by_learner[next(k for k, v in by_learner.items() if v[0]["label"] == "1")][0]
    assert (row["events"], row["active_days"], row["events_last_week"]) == ("3", "3", "0")


def test_export_stops_at_the_first_dropout_and_skips_silent_windows(tmp_path, quiz_and_code):
    mission = quiz_and_code[0]
    gone = _consenting("gone")
    _timeline(gone, [40, 38, 35])  # then silence for five weeks
    _open_mission(gone, mission)
    rows = _export(tmp_path)
    assert len(rows) == 1 and rows[0]["label"] == "1"  # no echo rows for the empty windows after


def test_export_skips_unknown_outcomes_and_finished_learners(tmp_path, quiz_and_code):
    mission = quiz_and_code[0]
    recent = _consenting("recent")  # first activity 20 days ago: horizon not over
    _timeline(recent, [20, 19])
    _open_mission(recent, mission, 20)
    finished = _consenting("finished")
    _timeline(finished, [40, 38, 35])
    Progress.objects.create(
        user=finished, mission=mission, status="completed", completed=True,
        started_at=timezone.now() - timedelta(days=40),
        completed_at=timezone.now() - timedelta(days=36),
    )
    assert _export(tmp_path) == []


def test_export_is_private_by_construction(tmp_path, quiz_and_code):
    mission = quiz_and_code[0]
    shy = _user("shy")  # no consent
    staff = _user("prof", is_staff=True)
    consenting = _consenting("consenting")
    for user in (shy, staff, consenting):
        _timeline(user, [40, 38, 35])
        _open_mission(user, mission)

    rows = _export(tmp_path)
    assert {r["learner"] for r in rows} and all("consenting" not in r["learner"] for r in rows)
    assert len({r["learner"] for r in rows}) == 1
    assert len({r["learner"] for r in _export(tmp_path, "--all-users")}) == 2  # staff never


def test_export_rejects_nonsense_windows(tmp_path):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("export_risk_features", "--out", str(tmp_path / "x.csv"), "--step-days", "0")
