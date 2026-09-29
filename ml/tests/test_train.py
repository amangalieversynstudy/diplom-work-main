"""Training, threshold choice and the JSON export, on synthetic snapshots."""

import json

import numpy as np
import pandas as pd
import pytest

from risk import train
from risk.schema import BASE_FEATURES, FEATURES, GROUP, LABEL, PERIOD, add_derived


def synthetic(learners=900, seed=1, snapshots=1):
    """Leavers click less and fade out; enough noise that AUC is high but not 1."""
    rng = np.random.default_rng(seed)
    rows = []
    for number in range(learners):
        leaves = rng.random() < 0.35
        for snapshot in range(snapshots):
            events = int(rng.poisson(35 if leaves else 110))
            days = int(min(14, rng.poisson(4 if leaves else 9)))
            recent = int(events * rng.uniform(0.0, 0.25 if leaves else 0.6))
            attempted = int(rng.poisson(2 if leaves else 4))
            failed = int(rng.binomial(attempted, 0.6 if leaves else 0.25))
            rows.append(
                {
                    GROUP: f"L{number}",
                    PERIOD: "P1" if number % 2 else "P2",
                    "active_days": days,
                    "events": events,
                    "events_last_week": recent,
                    "graded_attempted": attempted,
                    "graded_failed": failed,
                    LABEL: int(leaves),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def trained():
    return train.run(synthetic(), test_periods=["P2"], min_recall=0.8, seed=3)


def test_derived_features_handle_empty_denominators():
    frame = add_derived(
        pd.DataFrame(
            [
                {"events": 0, "events_last_week": 0, "graded_attempted": 0, "graded_failed": 0},
                {"events": 10, "events_last_week": 4, "graded_attempted": 4, "graded_failed": 1},
            ]
        )
    )
    assert list(frame["recent_share"]) == [0.0, 0.4]
    assert list(frame["graded_failed_share"]) == [0.0, 0.25]


def test_model_beats_the_single_feature_baseline(trained):
    _, _, report = trained
    logistic = report["models"]["logistic"]
    assert logistic["roc_auc"] > 0.9
    assert logistic["roc_auc"] >= report["baseline"]["roc_auc"] - 0.01
    assert set(report["models"]) == {"logistic", "boosting"}


def test_threshold_is_chosen_before_the_test_set_and_catches_leavers(trained):
    _, threshold, report = trained
    assert report["models"]["logistic"]["threshold"] == pytest.approx(threshold, abs=1e-4)
    # picked for recall 0.8 on validation; a held-out set lands near it
    assert report["models"]["logistic"]["recall"] >= 0.7


def test_pick_threshold_is_the_strictest_one_meeting_the_recall():
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    scores = np.array([0.9, 0.8, 0.6, 0.3, 0.7, 0.4, 0.2, 0.1])
    threshold = train.pick_threshold(y, scores, min_recall=0.75)
    assert threshold == pytest.approx(0.6)  # catches 3 of 4 leavers
    assert train.pick_threshold(y, scores, min_recall=1.0) == pytest.approx(0.3)


def test_period_split_keeps_test_rows_out_of_training():
    table = synthetic(learners=100)
    fit, test = train.split(table, ["P2"])
    assert set(test[PERIOD]) == {"P2"} and "P2" not in set(fit[PERIOD])
    with pytest.raises(ValueError):
        train.split(table, ["nope"])


def test_grouped_split_never_separates_a_learners_snapshots():
    table = synthetic(learners=200, snapshots=3)
    fit, test = train.split(table)
    assert not set(fit[GROUP]) & set(test[GROUP])
    assert len(fit) + len(test) == len(table)


def test_exported_json_scores_like_scikit_learn(trained):
    model, threshold, _ = trained
    exported = train.export_logistic(model, threshold, {"source": "test"})
    assert exported["features"] == list(FEATURES)

    frame = add_derived(synthetic(learners=50, seed=9))
    expected = model.predict_proba(frame[list(FEATURES)])[:, 1]
    by_hand = []
    for _, row in frame.iterrows():
        z = exported["intercept"]
        for name, mean, scale, coef in zip(
            exported["features"], exported["mean"], exported["scale"], exported["coef"]
        ):
            z += coef * (row[name] - mean) / scale
        by_hand.append(1 / (1 + np.exp(-z)))
    assert np.allclose(expected, by_hand, atol=1e-9)


def test_more_activity_lowers_the_risk(trained):
    _, _, report = trained
    coefficients = report["coefficients"]
    assert coefficients["events"] < 0 or coefficients["active_days"] < 0


def test_outputs_are_written(tmp_path, trained):
    model, threshold, report = trained
    meta = {"source": "synthetic", "target": "test", "window_days": 14,
            "horizon_days": 14, "trained_at": "2026-01-01T00:00:00+00:00"}
    train.write_outputs(tmp_path, model, threshold, report, meta)
    saved = json.loads((tmp_path / "model.json").read_text(encoding="utf-8"))
    assert saved["kind"] == "logistic" and saved["window_days"] == 14
    assert saved["metrics"]["roc_auc"] == report["models"]["logistic"]["roc_auc"]
    assert "Модель риска ухода" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_one_sided_data_is_reported_clearly():
    table = synthetic(learners=100)
    table[LABEL] = 1
    with pytest.raises(ValueError, match="only one outcome class"):
        train.run(table)


def test_platform_csv_must_have_the_contract_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"learner": ["a"], "label": [1]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="lacks columns"):
        train.load_features(path)


def test_base_features_are_the_documented_contract():
    assert BASE_FEATURES == (
        "active_days", "events", "events_last_week", "graded_attempted", "graded_failed",
    )
