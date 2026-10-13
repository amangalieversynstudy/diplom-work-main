"""The ablation script on a small synthetic table."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location(
    "oulad_ablation", Path(__file__).resolve().parents[1] / "scripts" / "oulad_ablation.py"
)
ablation_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ablation_script)


def synthetic(n=600, seed=1):
    rng = np.random.default_rng(seed)
    label = rng.integers(0, 2, n)
    days = rng.poisson(np.where(label == 1, 4, 8))
    table = pd.DataFrame({
        "learner": [f"s{i}" for i in range(n)],
        "period": np.where(np.arange(n) < n * 0.7, "2013J", "2014J"),
        "active_days": days,
        "events": days * 10 + rng.poisson(5, n),
        "events_last_week": rng.poisson(np.where(label == 1, 5, 15)),
        "graded_attempted": rng.integers(0, 3, n),
        "graded_failed": rng.integers(0, 2, n),
        "label": label,
    })
    table["graded_failed"] = np.minimum(table["graded_failed"], table["graded_attempted"])
    return table


def test_ablation_reports_intervals_and_is_reproducible():
    table = synthetic()
    first = ablation_script.ablation(table, ["2014J"], reps=30, seed=3)
    second = ablation_script.ablation(table, ["2014J"], reps=30, seed=3)
    assert first == second
    base = first["sets"][first["baseline"]]
    assert base["diff_vs_baseline"] == 0 and base["diff_ci"] == [0.0, 0.0]
    full = first["sets"]["полный набор"]
    assert full["ci"][0] <= full["roc_auc"] <= full["ci"][1] + 1e-9
    assert full["roc_auc"] > 0.6  # the synthetic signal is real
    assert full["diff_ci"][0] <= full["diff_ci"][1]
