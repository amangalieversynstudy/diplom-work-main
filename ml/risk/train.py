"""Train, evaluate and export the drop-out risk model.

    python -m risk.train --oulad path/to/oulad --out out/            (from ml/)
    python -m risk.train --features risk_features.csv --performance performance.csv --out out/

Two models are fitted on the same rows: a logistic regression (the one that is
exported, because a teacher can read its coefficients) and gradient boosting (a
yardstick: if it is much better, the linear model is leaving signal on the table).

The decision threshold is chosen on a validation split so that a target share of
the learners who really leave is caught, and is then *frozen* before the test set
is looked at. The test set is later presentations (OULAD) or unseen learners
(platform data), never rows of learners the model was trained on.

On the test rows the model is compared with the honest yardsticks on the *same* rows: the single feature
``active_days`` (low activity = high risk) and, for platform data, the platform's own rules (``rule_score``).
The differences in ROC AUC get a 95% interval from a paired bootstrap over learners. The pre-registered decision:
the model is connected only if the lower bound of the interval of "model minus the best yardstick" is above 0.

``--performance`` adds the forecast of the composite 50/30/20 score: one row per learner (features of the first
window, the score at the end of the period), compared with the train mean and a regression on ``active_days``.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
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
    PERFORMANCE_SCORE_COLUMN,
    RULE_SCORE_COLUMN,
    SCHEMA_VERSION,
    add_derived,
)

DEFAULT_MIN_RECALL = 0.8
DEFAULT_TEST_PERIOD = "2014J"  # the latest OULAD presentations
DEFAULT_BOOTSTRAP = 2000
MIN_REPLICATES = 100  # fewer usable bootstrap replicates than this: no interval
MIN_TEST_DEPARTURES = 10  # fewer departures among the test rows: the numbers are not interpretable
MIN_PERFORMANCE_LEARNERS = 8  # fewer learners with a final score: no train/test split for the score forecast


def load_features(path):
    """A platform export (``export_risk_features``) as a table with derived features.

    Extra columns (``rule_level``, ``rule_score``, ``performance_score``) are kept; ``rule_score`` is only a
    yardstick, never a feature."""
    table = pd.read_csv(path)
    missing = {GROUP, PERIOD, LABEL, *BASE_FEATURES} - set(table.columns)
    if missing:
        raise ValueError(f"{path} lacks columns: {sorted(missing)}")
    return table


def load_performance(path):
    """The per-learner table of ``export_risk_features --performance-out``: one row per learner."""
    table = pd.read_csv(path)
    missing = {GROUP, *BASE_FEATURES, PERFORMANCE_SCORE_COLUMN} - set(table.columns)
    if missing:
        raise ValueError(f"{path} lacks columns: {sorted(missing)}")
    if table[GROUP].duplicated().any():
        raise ValueError(f"{path}: expected one row per learner")
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


def _auc(y, scores):
    """ROC AUC by ranks (ties share their rank, as in scikit-learn); None with a single outcome class."""
    y = np.asarray(y, dtype=int)
    positives = int(y.sum())
    negatives = len(y) - positives
    if not positives or not negatives:
        return None
    ranks = rankdata(scores)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def _percentile_interval(values):
    """95% percentile interval of bootstrap draws, or (None, None) with too few of them."""
    values = np.asarray(values, dtype=float)
    if values.size < MIN_REPLICATES:
        return None, None
    return round(float(np.percentile(values, 2.5)), 4), round(float(np.percentile(values, 97.5)), 4)


COMPARISONS = (("model", "active_days"), ("model", "rules"), ("rules", "active_days"))


def compare_on_same_rows(groups, y, scores, *, replicates=DEFAULT_BOOTSTRAP, seed=0):
    """ROC AUC of each score on the test rows and the differences between them, with 95% intervals.

    ``scores`` maps a name (``model``, ``active_days``, ``rules``) to values aligned with ``y``, higher = more
    risk; NaN marks a row a score does not cover (no rule snapshot), and a comparison uses the rows both scores
    cover. The bootstrap is paired and clustered: each replicate draws learners with replacement (every row of a
    drawn learner goes in, as many times as it was drawn) and evaluates every comparison on that same draw.
    """
    groups = np.asarray(groups)
    y = np.asarray(y, dtype=int)
    scores = {name: np.asarray(values, dtype=float) for name, values in scores.items()}
    _, learner_of_row = np.unique(groups, return_inverse=True)
    n_learners = int(learner_of_row.max()) + 1 if len(groups) else 0
    pairs = [(a, b) for a, b in COMPARISONS if a in scores and b in scores]

    def covered(*names):
        mask = np.ones(len(y), dtype=bool)
        for name in names:
            mask &= np.isfinite(scores[name])
        return mask

    result = {
        "learners": n_learners,
        "rows": int(len(y)),
        "departures": int(y.sum()),
        "replicates": replicates,
        "auc": {},
        "differences": {},
    }
    for name in scores:
        mask = covered(name)
        auc = _auc(y[mask], scores[name][mask])
        result["auc"][name] = {"roc_auc": None if auc is None else round(auc, 4), "rows": int(mask.sum())}

    draws = {pair: [] for pair in pairs}
    masks = {pair: covered(*pair) for pair in pairs}
    rng = np.random.default_rng(seed)
    for _ in range(replicates if n_learners else 0):
        counts = np.bincount(rng.integers(0, n_learners, n_learners), minlength=n_learners)
        index = np.repeat(np.arange(len(y)), counts[learner_of_row])
        for pair in pairs:
            rows = index[masks[pair][index]]
            first, second = _auc(y[rows], scores[pair[0]][rows]), _auc(y[rows], scores[pair[1]][rows])
            if first is not None and second is not None:
                draws[pair].append(first - second)
    for pair in pairs:
        mask = masks[pair]
        first, second = _auc(y[mask], scores[pair[0]][mask]), _auc(y[mask], scores[pair[1]][mask])
        low, high = _percentile_interval(draws[pair])
        result["differences"][f"{pair[0]}-{pair[1]}"] = {
            "estimate": None if first is None or second is None else round(first - second, 4),
            "ci_low": low,
            "ci_high": high,
            "rows": int(mask.sum()),
            "replicates": len(draws[pair]),
        }

    # the pre-registered rule: connect the model only if it beats the best yardstick beyond doubt
    yardsticks = [name for name in ("active_days", "rules") if f"model-{name}" in result["differences"]]
    best = max(yardsticks, key=lambda name: result["auc"][name]["roc_auc"] or 0.0, default=None)
    versus = result["differences"].get(f"model-{best}", {}) if best else {}
    result["decision"] = {
        "best_yardstick": best,
        "connect_model": bool(versus.get("ci_low") is not None and versus["ci_low"] > 0),
    }
    result["few_departures"] = result["departures"] < MIN_TEST_DEPARTURES
    return result


def _regression_metrics(y, prediction):
    y = np.asarray(y, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    return {
        "mae": float(mean_absolute_error(y, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(y, prediction))),
        "r2": float(r2_score(y, prediction)) if len(y) > 1 and np.var(y) > 0 else None,
    }


def _ridge():
    return make_pipeline(StandardScaler(), Ridge(alpha=1.0))


def _ridge_weights(pipeline):
    scaler, ridge = pipeline.named_steps["standardscaler"], pipeline.named_steps["ridge"]
    return {
        "mean": [float(v) for v in scaler.mean_],
        "scale": [float(v) if v else 1.0 for v in scaler.scale_],
        "coef": [round(float(v), 4) for v in ridge.coef_],
        "intercept": round(float(ridge.intercept_), 4),
    }


def forecast_performance(table, *, seed=0, replicates=DEFAULT_BOOTSTRAP):
    """The score forecast on the per-learner table, against two yardsticks, with bootstrap intervals.

    Learners are split into train and test (one row each). The model is the ridge regression on the six
    features; the yardsticks are the train mean and a regression on ``active_days`` alone. Intervals resample the
    test learners; a difference below 0 in MAE (or above 0 in R2) means the model is better.
    """
    table = add_derived(table.dropna(subset=[PERFORMANCE_SCORE_COLUMN]))
    if len(table) < MIN_PERFORMANCE_LEARNERS:
        raise ValueError(
            f"only {len(table)} learner(s) with a final score: too few to split into train and test "
            f"(need at least {MIN_PERFORMANCE_LEARNERS})"
        )
    train, test = _grouped_split(table, 0.25, seed)
    y_train = train[PERFORMANCE_SCORE_COLUMN].astype(float).to_numpy()
    y_test = test[PERFORMANCE_SCORE_COLUMN].astype(float).to_numpy()
    model = _ridge().fit(train[list(FEATURES)], y_train)
    activity = LinearRegression().fit(train[["active_days"]], y_train)
    predictions = {
        "model": np.clip(model.predict(test[list(FEATURES)]), 0.0, 100.0),
        "mean": np.full(len(test), float(y_train.mean())),
        "active_days": np.clip(activity.predict(test[["active_days"]]), 0.0, 100.0),
    }

    samples = {name: {"mae": [], "r2": []} for name in predictions}
    differences = {f"model-{name}": {"mae": [], "r2": []} for name in ("mean", "active_days")}
    rng = np.random.default_rng(seed)
    for _ in range(replicates):
        index = rng.integers(0, len(y_test), len(y_test))
        metrics = {name: _regression_metrics(y_test[index], values[index]) for name, values in predictions.items()}
        for name, m in metrics.items():
            samples[name]["mae"].append(m["mae"])
            if m["r2"] is not None:
                samples[name]["r2"].append(m["r2"])
        for name in ("mean", "active_days"):
            key = f"model-{name}"
            differences[key]["mae"].append(metrics["model"]["mae"] - metrics[name]["mae"])
            if metrics["model"]["r2"] is not None and metrics[name]["r2"] is not None:
                differences[key]["r2"].append(metrics["model"]["r2"] - metrics[name]["r2"])

    def rounded(value, digits=3):
        return None if value is None else round(value, digits)

    point = {name: _regression_metrics(y_test, values) for name, values in predictions.items()}
    result = {
        "design": "per_learner",
        "learners": {"train": int(len(train)), "test": int(len(test))},
        "replicates": replicates,
        "models": {},
        "differences": {},
        **_ridge_weights(model),
    }
    for name, m in point.items():
        result["models"][name] = {
            "mae": rounded(m["mae"]),
            "rmse": rounded(m["rmse"]),
            "r2": rounded(m["r2"], 4),
            "mae_ci": _percentile_interval(samples[name]["mae"]),
            "r2_ci": _percentile_interval(samples[name]["r2"]),
        }
    for key, values in differences.items():
        name = key.split("-", 1)[1]
        r2_model, r2_other = point["model"]["r2"], point[name]["r2"]
        result["differences"][key] = {
            "mae": rounded(point["model"]["mae"] - point[name]["mae"]),
            "mae_ci": _percentile_interval(values["mae"]),
            "r2": None if r2_model is None or r2_other is None else round(r2_model - r2_other, 4),
            "r2_ci": _percentile_interval(values["r2"]),
        }
    # the old field names stay for readers of earlier reports
    result.update(mae=result["models"]["model"]["mae"], rmse=result["models"]["model"]["rmse"],
                  r2=result["models"]["model"]["r2"])
    return result


def _row_level_regression(train, test):
    """The score regression on the snapshot rows (several per learner): kept for exports without the per-learner
    table, but it is not the forecast design (see ``forecast_performance``)."""
    regression = _ridge().fit(train[list(FEATURES)], train[PERFORMANCE_SCORE_COLUMN].astype(float))
    prediction = np.clip(regression.predict(test[list(FEATURES)]), 0.0, 100.0)
    metrics = _regression_metrics(test[PERFORMANCE_SCORE_COLUMN].astype(float).to_numpy(), prediction)
    return {
        "design": "row_level",
        "mae": round(metrics["mae"], 3),
        "rmse": round(metrics["rmse"], 3),
        "r2": None if metrics["r2"] is None else round(metrics["r2"], 4),
        **_ridge_weights(regression),
    }


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


def run(
    table, *, test_periods=None, min_recall=DEFAULT_MIN_RECALL, seed=0, performance=None,
    replicates=DEFAULT_BOOTSTRAP,
):
    """Fit, evaluate and return ``(model, threshold, report)``.

    ``performance`` is the per-learner table for the score forecast (``load_performance``).
    """
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
    test_scores = {}
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
        test_scores[name] = scores
    report["baseline"] = single_feature_baseline(test)

    # the same test rows for the model and the yardsticks: low activity = high risk, the rules' own score
    yardsticks = {"model": test_scores["logistic"], "active_days": -test["active_days"].astype(float).to_numpy()}
    if RULE_SCORE_COLUMN in test.columns and pd.to_numeric(test[RULE_SCORE_COLUMN], errors="coerce").notna().any():
        yardsticks["rules"] = pd.to_numeric(test[RULE_SCORE_COLUMN], errors="coerce").to_numpy(dtype=float)
    report["comparison"] = compare_on_same_rows(
        test[GROUP].to_numpy(), test[LABEL].to_numpy(), yardsticks, replicates=replicates, seed=seed
    )

    logistic_model, threshold = fitted["logistic"]
    coefficients = logistic_model.named_steps["logisticregression"].coef_[0]
    report["coefficients"] = {
        name: round(float(value), 4) for name, value in zip(FEATURES, coefficients)
    }
    if performance is not None:
        report["performance_regression"] = forecast_performance(performance, seed=seed, replicates=replicates)
    elif PERFORMANCE_SCORE_COLUMN in table.columns and table[PERFORMANCE_SCORE_COLUMN].notna().any():
        report["performance_regression"] = _row_level_regression(train, test)
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
    if report.get("comparison"):
        lines += _comparison_lines(report["comparison"])
    if report.get("performance_regression"):
        lines += _performance_lines(report["performance_regression"])
    return "\n".join(lines) + "\n"


def _ci(interval):
    low, high = interval if interval else (None, None)
    return "—" if low is None else f"{low}…{high}"


NAMES = {"model": "модель", "active_days": "только active_days", "rules": "правила платформы", "mean": "среднее"}


def _comparison_lines(c):
    lines = [
        "",
        "## Модель против простых планок на тех же строках",
        "",
        f"Тест: {c['learners']} учеников, {c['rows']} строк, уходов {c['departures']}. Интервалы — парный бутстреп "
        f"по ученикам ({c['replicates']} повторов): все строки выбранного ученика входят в повтор вместе.",
    ]
    if c["few_departures"]:
        lines += [
            "",
            f"**Уходов в тесте меньше {MIN_TEST_DEPARTURES}: числа ниже не интерпретируются, они показывают только, "
            "что конвейер прошёл на этих данных.**",
        ]
    lines += ["", "| Оценка риска | ROC AUC | Строк |", "|---|---|---|"]
    for name, value in c["auc"].items():
        lines.append(f"| {NAMES.get(name, name)} | {value['roc_auc']} | {value['rows']} |")
    lines += ["", "| Разница ROC AUC | Оценка | 95% ДИ | Строк | Повторов |", "|---|---|---|---|---|"]
    for key, d in c["differences"].items():
        first, second = key.split("-", 1)
        lines.append(
            f"| {NAMES.get(first, first)} − {NAMES.get(second, second)} | {d['estimate']} | "
            f"{_ci((d['ci_low'], d['ci_high']))} | {d['rows']} | {d['replicates']} |"
        )
    decision = c["decision"]
    lines += [
        "",
        "Правило решения, записанное до пилота: модель подключается (`RISK_MODEL_PATH`), только если нижняя граница "
        "95% ДИ разницы ROC AUC модели и лучшей из планок выше 0. "
        f"Лучшая планка: {NAMES.get(decision['best_yardstick'], decision['best_yardstick'])}; решение: "
        f"**{'подключать' if decision['connect_model'] else 'не подключать, остаются правила'}**.",
    ]
    return lines


def _performance_lines(p):
    lines = ["", "## Прогноз сводного балла 50/30/20", ""]
    if p.get("design") != "per_learner":
        return lines + [
            f"MAE {p['mae']}, RMSE {p['rmse']}, R² {p['r2']} — по строкам выгрузки, по нескольку на ученика. Это не "
            "дизайн прогноза: для него нужна таблица по ученикам (`--performance`, из `export_risk_features "
            "--performance-out`)."
        ]
    lines += [
        f"Одна строка на ученика: признаки первого окна, балл на конец периода. Обучение {p['learners']['train']}, "
        f"тест {p['learners']['test']} учеников; интервалы — бутстреп по ученикам теста ({p['replicates']} повторов).",
        "",
        "| Прогноз | MAE | 95% ДИ MAE | RMSE | R² | 95% ДИ R² |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in p["models"].items():
        lines.append(
            f"| {NAMES.get(name, name)} | {m['mae']} | {_ci(m['mae_ci'])} | {m['rmse']} | {m['r2']} | {_ci(m['r2_ci'])} |"
        )
    lines += ["", "| Модель минус планка | ΔMAE | 95% ДИ | ΔR² | 95% ДИ |", "|---|---|---|---|---|"]
    for key, d in p["differences"].items():
        other = key.split("-", 1)[1]
        lines.append(f"| {NAMES.get(other, other)} | {d['mae']} | {_ci(d['mae_ci'])} | {d['r2']} | {_ci(d['r2_ci'])} |")
    lines += [
        "",
        "ΔMAE меньше 0 и ΔR² больше 0 — модель лучше планки; интервал, накрывающий 0, — разницы не видно. R² больше 0 "
        "значит лишь «лучше константы».",
    ]
    return lines


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
    parser.add_argument(
        "--performance", help="Per-learner CSV from `export_risk_features --performance-out` (platform only)."
    )
    parser.add_argument("--bootstrap", type=int, default=DEFAULT_BOOTSTRAP, help="Bootstrap replicates.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.performance and args.oulad:
        parser.error("--performance goes with --features (platform data), not with --oulad")

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
        table, test_periods=test_periods, min_recall=args.min_recall, seed=args.seed,
        performance=load_performance(args.performance) if args.performance else None,
        replicates=args.bootstrap,
    )
    exported = write_outputs(args.out, model, threshold, report, meta)
    print(json.dumps(exported["metrics"], indent=2))


if __name__ == "__main__":
    main()
