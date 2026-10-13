"""Window sweep and feature ablation for the OULAD risk model.

    python -I ml/scripts/oulad_ablation.py --oulad ml/data/oulad --out-root ml/data \
        --windows 14 21 28 42 --ablation-window 28 --boot 300 --seed 0

For every window the standard training run is repeated (outputs go to
``<out-root>/out_oulad_w<N>/``). For the ablation window, feature groups are
compared on the same test rows, and ROC AUC intervals come from a bootstrap
over test students, paired between models so the AUC difference is meaningful.
Only numpy, pandas and scikit-learn are used.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk import oulad, train  # noqa: E402
from risk.schema import FEATURES, LABEL, add_derived  # noqa: E402

GROUPS = {
    "activity": ["active_days", "events", "events_last_week", "recent_share"],
    "grades": ["graded_attempted", "graded_failed_share"],
}
# name -> features; "active_days" alone is the simple counter (score = -active_days)
SETS = {
    "active_days (один счётчик)": ["active_days"],
    "active_days + graded_attempted (базовая линия)": ["active_days", "graded_attempted"],
    "только активность": GROUPS["activity"],
    "только оценки/сдачи": GROUPS["grades"],
    "полный набор": list(FEATURES),
    "полный без активности по дням": [f for f in FEATURES if f != "active_days"],
    "полный без оценок/сдач": [f for f in FEATURES if f not in GROUPS["grades"]],
}


def scores_for(features, fit, test):
    if features == ["active_days"]:
        return -test["active_days"].to_numpy(dtype=float)  # fewer active days = more risk
    model = train.logistic()
    model.fit(fit[features], fit[LABEL])
    return model.predict_proba(test[features])[:, 1]


def bootstrap(y, score_map, baseline, reps, seed):
    """Paired bootstrap over students: AUC interval per model, difference vs baseline."""
    rng = np.random.default_rng(seed)
    n = len(y)
    draws = {name: [] for name in score_map}
    diffs = {name: [] for name in score_map}
    done = 0
    while done < reps:
        idx = rng.integers(0, n, n)
        if len(np.unique(y[idx])) < 2:
            continue
        aucs = {name: roc_auc_score(y[idx], s[idx]) for name, s in score_map.items()}
        for name, auc in aucs.items():
            draws[name].append(auc)
            diffs[name].append(auc - aucs[baseline])
        done += 1

    def interval(values):
        low, high = np.percentile(values, [2.5, 97.5])
        return [round(float(low), 4), round(float(high), 4)]

    result = {}
    for name, s in score_map.items():
        result[name] = {
            "roc_auc": round(float(roc_auc_score(y, s)), 4),
            "ci": interval(draws[name]),
            "diff_vs_baseline": round(float(roc_auc_score(y, s) - roc_auc_score(y, score_map[baseline])), 4),
            "diff_ci": interval(diffs[name]),
        }
    return result


def ablation(table, test_periods, reps, seed):
    table = add_derived(table)
    fit, test = train.split(table, test_periods, seed)
    y = test[LABEL].to_numpy()
    score_map = {name: scores_for(cols, fit, test) for name, cols in SETS.items()}
    baseline = next(iter(SETS))
    return {
        "n_test": int(len(y)),
        "bootstrap_reps": reps,
        "seed": seed,
        "baseline": baseline,
        "sets": bootstrap(y, score_map, baseline, reps, seed),
    }


def sweep_row(report, window):
    m = report["models"]["logistic"]
    return {
        "window_days": window,
        "n_test": m["n"],
        "base_rate": m["base_rate"],
        "roc_auc": m["roc_auc"],
        "pr_auc": m["pr_auc"],
        "brier": m["brier"],
        "threshold": m["threshold"],
        "precision": m["precision"],
        "recall": m["recall"],
        "flagged_share": m["flagged_share"],
        "boosting_roc_auc": report["models"]["boosting"]["roc_auc"],
        "best_single_feature": report["baseline"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--oulad", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--windows", type=int, nargs="+", default=[14, 21, 28, 42])
    parser.add_argument("--ablation-window", type=int, default=28)
    parser.add_argument("--test-periods", nargs="*", default=[train.DEFAULT_TEST_PERIOD])
    parser.add_argument("--boot", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    root = Path(args.out_root)
    rows, ablations = [], {}
    for window in args.windows:
        table = oulad.build_snapshots(args.oulad, window)
        model, threshold, report = train.run(table, test_periods=args.test_periods, seed=args.seed)
        meta = {
            "source": "OULAD",
            "target": "final outcome (Fail or Withdrawn)",
            "window_days": window,
            "horizon_days": None,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        train.write_outputs(root / f"out_oulad_w{window}", model, threshold, report, meta)
        rows.append(sweep_row(report, window))
        ablations[str(window)] = ablation(table, args.test_periods, args.boot, args.seed)
    result = {"sweep": rows, "ablation": ablations, "ablation_window": args.ablation_window}
    (root / "oulad_sweep_ablation.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(rows, indent=1, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
