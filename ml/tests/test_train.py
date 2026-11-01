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


def test_continuous_performance_score_regression_is_fitted_when_present():
    table = synthetic(learners=200, seed=5)
    table["performance_score"] = np.clip(
        85.0 - 40.0 * table[LABEL] + 0.2 * table["events"] - 5.0 * table["graded_failed"],
        0.0,
        100.0,
    )
    _, _, report = train.run(table, test_periods=["P2"], min_recall=0.8, seed=3)
    assert "performance_regression" in report
    perf_reg = report["performance_regression"]
    assert perf_reg["mae"] < 20.0
    assert perf_reg["r2"] is not None and perf_reg["r2"] > 0.3
    assert len(perf_reg["coef"]) == len(FEATURES)
    assert perf_reg["design"] == "row_level"  # snapshot rows, not the per-learner forecast design


# ── the model against simple yardsticks on the same rows ────────────────────


def test_comparison_without_rules_puts_the_model_against_active_days(trained):
    _, _, report = trained
    comparison = report["comparison"]
    assert set(comparison["auc"]) == {"model", "active_days"}
    assert set(comparison["differences"]) == {"model-active_days"}
    # leavers have fewer active days, so "minus active_days" ranks them above chance
    assert comparison["auc"]["active_days"]["roc_auc"] > 0.6
    difference = comparison["differences"]["model-active_days"]
    assert difference["ci_low"] <= difference["estimate"] <= difference["ci_high"]
    assert comparison["few_departures"] is False


def test_comparison_uses_the_rule_score_on_the_rows_it_covers():
    table = synthetic(learners=300, seed=4)
    rng = np.random.default_rng(0)
    rules = np.where(table[LABEL] == 1, rng.integers(2, 6, len(table)), rng.integers(0, 4, len(table))).astype(float)
    rules[::5] = np.nan  # no snapshot before these anchors
    table["rule_score"] = rules
    _, _, report = train.run(table, test_periods=["P2"], seed=3, replicates=300)
    comparison = report["comparison"]
    assert set(comparison["differences"]) == {"model-active_days", "model-rules", "rules-active_days"}
    assert comparison["auc"]["rules"]["rows"] < comparison["auc"]["model"]["rows"]
    assert comparison["differences"]["model-rules"]["rows"] == comparison["auc"]["rules"]["rows"]
    assert comparison["decision"]["best_yardstick"] in {"rules", "active_days"}


def test_bootstrap_is_deterministic_and_resamples_learners_not_rows():
    groups = np.repeat(["a", "b", "c", "d", "e", "f"], 3)
    y = np.repeat([1, 1, 1, 0, 0, 0], 3)
    scores = {"model": np.repeat([0.9, 0.8, 0.4, 0.5, 0.2, 0.1], 3), "active_days": -np.repeat([1, 3, 2, 4, 6, 5], 3.0)}
    first = train.compare_on_same_rows(groups, y, scores, replicates=500, seed=7)
    again = train.compare_on_same_rows(groups, y, scores, replicates=500, seed=7)
    assert first == again
    assert first["learners"] == 6 and first["rows"] == 18 and first["departures"] == 9
    # draws with only leavers or only stayers have one class and are skipped
    assert first["differences"]["model-active_days"]["replicates"] < 500
    assert first["few_departures"] is True


def test_the_model_is_connected_only_when_it_beats_the_best_yardstick_beyond_doubt():
    rng = np.random.default_rng(1)
    groups = np.arange(400).astype(str)
    y = rng.integers(0, 2, 400)
    perfect = y + rng.uniform(0, 0.1, 400)
    noise = rng.uniform(0, 1, 400)
    decision = train.compare_on_same_rows(groups, y, {"model": perfect, "active_days": noise}, replicates=300)
    assert decision["decision"] == {"best_yardstick": "active_days", "connect_model": True}
    tie = train.compare_on_same_rows(groups, y, {"model": noise, "active_days": perfect}, replicates=300)
    assert tie["decision"]["connect_model"] is False


def test_rank_auc_matches_scikit_learn():
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 200)
    scores = np.round(rng.normal(size=200), 1)  # with ties
    assert train._auc(y, scores) == pytest.approx(roc_auc_score(y, scores))
    assert train._auc(np.ones(5), np.arange(5)) is None


# ── the score forecast, one row per learner ─────────────────────────────────


def per_learner(learners=160, seed=6):
    table = synthetic(learners=learners, seed=seed).drop(columns=[LABEL, PERIOD])
    rng = np.random.default_rng(seed)
    table["performance_score"] = np.clip(20 + 0.35 * table["events"] + 2.0 * table["active_days"]
                                         + rng.normal(0, 6, len(table)), 0, 100)
    return table


def test_per_learner_forecast_reports_the_model_and_both_yardsticks():
    result = train.forecast_performance(per_learner(), seed=1, replicates=300)
    assert result["design"] == "per_learner"
    assert result["learners"]["train"] + result["learners"]["test"] == 160
    assert set(result["models"]) == {"model", "mean", "active_days"}
    assert set(result["differences"]) == {"model-mean", "model-active_days"}
    model, mean = result["models"]["model"], result["models"]["mean"]
    assert model["mae"] < mean["mae"] and model["r2"] > 0.3 and mean["r2"] <= 0.05
    low, high = result["differences"]["model-mean"]["mae_ci"]
    assert low < high < 0  # clearly better than the mean
    assert result["mae"] == model["mae"]  # the old field names stay


def test_per_learner_forecast_refuses_too_few_learners():
    with pytest.raises(ValueError, match="too few"):
        train.forecast_performance(per_learner(learners=5), seed=0)


def test_performance_table_needs_one_row_per_learner(tmp_path):
    table = per_learner(learners=10)
    path = tmp_path / "performance.csv"
    pd.concat([table, table.head(1)]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="one row per learner"):
        train.load_performance(path)


def test_cli_writes_both_new_sections(tmp_path):
    risk_path, perf_path = tmp_path / "risk.csv", tmp_path / "performance.csv"
    table = synthetic(learners=300, seed=8)
    table["rule_score"] = np.where(table[LABEL] == 1, 4.0, 1.0)
    table["rule_level"] = np.where(table[LABEL] == 1, "high", "ok")
    table.to_csv(risk_path, index=False)
    per_learner().to_csv(perf_path, index=False)
    train.main(["--features", str(risk_path), "--performance", str(perf_path), "--bootstrap", "200",
                "--out", str(tmp_path / "out")])
    text = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "Модель против простых планок" in text and "правила платформы" in text
    assert "Прогноз сводного балла 50/30/20" in text and "Одна строка на ученика" in text
    saved = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert saved["performance_regression"]["design"] == "per_learner"
    model = json.loads((tmp_path / "out" / "model.json").read_text(encoding="utf-8"))
    assert model["source"] == "platform" and model["kind"] == "logistic" and model["features"] == list(FEATURES)
