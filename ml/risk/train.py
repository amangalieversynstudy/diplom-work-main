"""Train, evaluate and export the drop-out risk model.

    python -m risk.train --oulad path/to/oulad --out out/            (from ml/)
    python -m risk.train --features risk_features.csv --out out/

Two models are fitted on the same rows: a logistic regression (the one that is
exported, because a teacher can read its coefficients) and gradient boosting (a
yardstick: if it is much better, the linear model is leaving signal on the table).

The decision threshold is chosen on a validation split so that a target share of
the learners who really leave is caught, and is then *frozen* before the test set
is looked at. The test set is later presentations (OULAD) or unseen learners
(platform data), never rows of learners the model was trained on.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import oulad
from .schema import (
    BASE_FEATURES,
    FEATURES,
    GROUP,
    LABEL,
    PERIOD,
    SCHEMA_VERSION,
    add_derived,
)

DEFAULT_MIN_RECALL = 0.8
DEFAULT_TEST_PERIOD = "2014J"  # the latest OULAD presentations


def load_features(path):
    """A platform export (``export_risk_features``) as a table with derived features."""
    table = pd.read_csv(path)
    missing = {GROUP, PERIOD, LABEL, *BASE_FEATURES} - set(table.columns)
    if missing:
        raise ValueError(f"{path} lacks columns: {sorted(missing)}")
    return table


def split(table, test_periods=None, seed=0):
    """(train, test). By period when ``test_periods`` is given, else by learner."""
    if test_periods:
        wanted = {str(period) for period in test_periods}
        is_test = table[PERIOD].astype(str).isin(wanted)
        train, test = table[~is_test], table[is_test]
        if train.empty or test.empty:
            raise ValueError(f"the test periods {sorted(wanted)} leave no train or test rows")
        return train, test
    return _grouped_split(table, 0.25, seed)


def _grouped_split(table, share, seed):
    splitter = GroupShuffleSplit(n_splits=1, test_size=share, random_state=seed)
    first, second = next(splitter.split(table, groups=table[GROUP]))
    return table.iloc[first], table.iloc[second]


def logistic():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0),
    )


def boosting(seed=0):
    return HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.1, max_iter=200, class_weight="balanced",
        random_state=seed,
    )


def pick_threshold(y_true, scores, min_recall=DEFAULT_MIN_RECALL):
    """The strictest threshold that still catches ``min_recall`` of those who leave."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    eligible = thresholds[recall[:-1] >= min_recall]
    return float(eligible.max()) if len(eligible) else float(thresholds.min())


def evaluate(y_true, scores, threshold):
    """Ranking quality (AUC) and what the frozen threshold does."""
    y_true = np.asarray(y_true)
    flagged = np.asarray(scores) >= threshold
    caught = int((flagged & (y_true == 1)).sum())
    leavers = int((y_true == 1).sum())
    both_classes = 0 < leavers < len(y_true)
    return {
        "n": int(len(y_true)),
        "base_rate": round(float(y_true.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y_true, scores)), 4) if both_classes else None,
        "pr_auc": round(float(average_precision_score(y_true, scores)), 4) if both_classes else None,
        "brier": round(float(brier_score_loss(y_true, scores)), 4),
        "threshold": round(float(threshold), 4),
        "flagged_share": round(float(flagged.mean()), 4),
        "precision": round(caught / flagged.sum(), 4) if flagged.sum() else None,
        "recall": round(caught / leavers, 4) if leavers else None,
    }


def single_feature_baseline(frame):
    """Best ROC AUC any single feature reaches alone (direction-free).

    The honest yardstick: a model that cannot beat "just count the clicks" is not
    worth a teacher's attention.
    """
    y = frame[LABEL]
    if y.nunique() < 2:
        return {"feature": None, "roc_auc": None}
    best = {"feature": None, "roc_auc": 0.0}
    for name in FEATURES:
        auc = roc_auc_score(y, frame[name])
        auc = max(auc, 1 - auc)
        if auc > best["roc_auc"]:
            best = {"feature": name, "roc_auc": round(float(auc), 4)}
    return best


def export_logistic(pipeline, threshold, meta):
    """Plain-JSON model that the Django backend can score without scikit-learn."""
    scaler = pipeline.named_steps["standardscaler"]
    regression = pipeline.named_steps["logisticregression"]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "logistic",
        "features": list(FEATURES),
        "mean": [float(v) for v in scaler.mean_],
        "scale": [float(v) if v else 1.0 for v in scaler.scale_],
        "coef": [float(v) for v in regression.coef_[0]],
        "intercept": float(regression.intercept_[0]),
        "threshold": float(threshold),
        **meta,
    }


def run(table, *, test_periods=None, min_recall=DEFAULT_MIN_RECALL, seed=0):
    """Fit, evaluate and return ``(model_json, report)``."""
    table = add_derived(table)
    train, test = split(table, test_periods, seed)
    fit, validation = _grouped_split(train, 0.2, seed)
    for name, part in (("train", fit), ("validation", validation)):
        if part[LABEL].nunique() < 2:
            raise ValueError(
                f"the {name} rows contain only one outcome class: the data is too small "
                "or too one-sided to train on"
            )

    report = {
        "rows": {"train": len(fit), "validation": len(validation), "test": len(test)},
        "min_recall": min_recall,
        "features": list(FEATURES),
        "models": {},
    }
    fitted = {}
    for name, model in (("logistic", logistic()), ("boosting", boosting(seed))):
        model.fit(fit[list(FEATURES)], fit[LABEL])
        threshold = pick_threshold(
            validation[LABEL], model.predict_proba(validation[list(FEATURES)])[:, 1], min_recall
        )
        # the final model sees train + validation; the threshold stays as chosen
        model.fit(train[list(FEATURES)], train[LABEL])
        scores = model.predict_proba(test[list(FEATURES)])[:, 1]
        report["models"][name] = evaluate(test[LABEL], scores, threshold)
        fitted[name] = (model, threshold)
    report["baseline"] = single_feature_baseline(test)

    logistic_model, threshold = fitted["logistic"]
    coefficients = logistic_model.named_steps["logisticregression"].coef_[0]
    report["coefficients"] = {
        name: round(float(value), 4) for name, value in zip(FEATURES, coefficients)
    }
    return logistic_model, threshold, report


def write_outputs(out, model, threshold, report, meta):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    exported = export_logistic(model, threshold, {**meta, "metrics": report["models"]["logistic"]})
    (out / "model.json").write_text(json.dumps(exported, indent=2), encoding="utf-8")
    report = {**report, "meta": meta}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "report.md").write_text(render_report(report), encoding="utf-8")
    return exported


def render_report(report):
    meta = report["meta"]
    lines = [
        "# Модель риска ухода: отчёт об обучении",
        "",
        f"Источник: **{meta['source']}**, окно {meta['window_days']} дн., "
        f"цель: {meta['target']}. Дата: {meta['trained_at']}.",
        f"Строк: обучение {report['rows']['train']}, валидация "
        f"{report['rows']['validation']}, тест {report['rows']['test']}.",
        f"Порог выбран на валидации так, чтобы поймать не меньше "
        f"{int(report['min_recall'] * 100)}% ушедших, и зафиксирован до проверки на тесте.",
        "",
        "| Модель | ROC AUC | PR AUC | Precision | Recall | Доля помеченных |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in report["models"].items():
        lines.append(
            f"| {name} | {m['roc_auc']} | {m['pr_auc']} | {m['precision']} | "
            f"{m['recall']} | {m['flagged_share']} |"
        )
    base = report["baseline"]
    lines += [
        "",
        f"Доля ушедших в тесте: {report['models']['logistic']['base_rate']}. "
        f"Лучший одиночный признак (`{base['feature']}`) даёт ROC AUC {base['roc_auc']}: "
        "модель должна его превосходить.",
        "",
        "Коэффициенты логистической модели (стандартизованные признаки; плюс — риск растёт):",
        "",
    ]
    lines += [f"- `{name}`: {value}" for name, value in report["coefficients"].items()]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--oulad", help="Directory with the OULAD csv files.")
    source.add_argument("--features", help="CSV from `manage.py export_risk_features`.")
    parser.add_argument(
        "--window-days", type=int, default=None,
        help="Feature window (OULAD default 28; platform default 14, as in the export).",
    )
    parser.add_argument("--horizon-days", type=int, default=14, help="Platform export horizon.")
    parser.add_argument("--test-periods", nargs="*", default=None)
    parser.add_argument("--min-recall", type=float, default=DEFAULT_MIN_RECALL)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    window = args.window_days or (28 if args.oulad else 14)
    if args.oulad:
        table = oulad.build_snapshots(args.oulad, window)
        test_periods = args.test_periods or [DEFAULT_TEST_PERIOD]
        meta = {
            "source": "OULAD",
            "target": "final outcome (Fail or Withdrawn)",
            "window_days": window,
            "horizon_days": None,
        }
    else:
        table = load_features(args.features)
        test_periods = args.test_periods
        meta = {
            "source": "platform",
            "target": f"no activity in the next {args.horizon_days} days",
            "window_days": window,
            "horizon_days": args.horizon_days,
        }
    meta["trained_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    model, threshold, report = run(
        table, test_periods=test_periods, min_recall=args.min_recall, seed=args.seed
    )
    exported = write_outputs(args.out, model, threshold, report, meta)
    print(json.dumps(exported["metrics"], indent=2))


if __name__ == "__main__":
    main()
