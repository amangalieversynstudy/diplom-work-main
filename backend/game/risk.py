"""Drop-out risk from the learner's recent activity, scored in plain Python.

The model is trained offline (``ml/``) and shipped as a small JSON file, so the
web server needs neither numpy nor scikit-learn: a logistic regression is a dot
product and a sigmoid. Point ``RISK_MODEL_PATH`` at the file to switch it on;
without it the early-warning list simply works from its rules.

The feature contract lives in ``ml/risk/schema.py``; ``FEATURES`` below must
match it (a test compares them).
"""

import json
import logging
import math
from datetime import timedelta
from pathlib import Path

from django.conf import settings

from .models import CodeRun, LearningEvent

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
BASE_FEATURES = (
    "active_days",
    "events",
    "events_last_week",
    "graded_attempted",
    "graded_failed",
)
FEATURES = (
    "active_days",
    "events",
    "events_last_week",
    "recent_share",
    "graded_attempted",
    "graded_failed_share",
)


class RiskModel:
    """A logistic regression over standardised features."""

    def __init__(self, data):
        if data.get("schema_version") != SCHEMA_VERSION or data.get("kind") != "logistic":
            raise ValueError("unsupported model file")
        if data.get("source") != "platform":
            raise ValueError(
                "the model was not trained on this platform's data; a model fitted "
                "on another dataset predicts another outcome"
            )
        if list(data.get("features", [])) != list(FEATURES):
            raise ValueError("model features do not match the platform's features")
        self.mean = [float(v) for v in data["mean"]]
        self.scale = [float(v) for v in data["scale"]]
        self.coef = [float(v) for v in data["coef"]]
        self.intercept = float(data["intercept"])
        self.threshold = float(data["threshold"])
        self.window_days = int(data["window_days"])
        self.horizon_days = data.get("horizon_days")
        if not {len(self.mean), len(self.scale), len(self.coef)} == {len(FEATURES)}:
            raise ValueError("model vectors have the wrong length")
        if any(s == 0 or not math.isfinite(s) for s in self.scale) or self.window_days < 1:
            raise ValueError("model scale or window is invalid")

    def probability(self, features):
        z = self.intercept
        for name, mean, scale, coef in zip(FEATURES, self.mean, self.scale, self.coef):
            z += coef * (features[name] - mean) / scale
        if z >= 0:
            return 1 / (1 + math.exp(-z))
        e = math.exp(z)
        return e / (1 + e)


_loaded = {"key": None, "model": None}


def load_risk_model():
    """The configured model, or None (unset, missing or invalid: never raises)."""
    path = getattr(settings, "RISK_MODEL_PATH", "")
    if not path:
        return None
    try:
        key = (path, Path(path).stat().st_mtime_ns)
    except OSError:
        key = (path, None)
    if _loaded["key"] == key:
        return _loaded["model"]
    model = None
    if key[1] is not None:
        try:
            model = RiskModel(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            logger.exception("Ignoring the risk model at %s", path)
    else:
        logger.warning("RISK_MODEL_PATH %s does not exist", path)
    _loaded.update(key=key, model=model)
    return model


# ── features ────────────────────────────────────────────────────────────────


def activity_rows(user_ids, since=None, until=None):
    """{user_id: [(timestamp, graded, failed)]} of everything the learners did.

    ``graded`` marks a counted graded attempt (a quiz answer or a graded code
    run made before the step was solved); ``failed`` marks the unsuccessful ones.
    """
    rows = {user_id: [] for user_id in user_ids}

    def bounded(queryset):
        if since is not None:
            queryset = queryset.filter(created_at__gte=since)
        if until is not None:
            queryset = queryset.filter(created_at__lt=until)
        return queryset

    events = bounded(LearningEvent.objects.filter(user_id__in=rows))
    for user_id, stamp, kind, meta in events.values_list(
        "user_id", "created_at", "event_type", "meta"
    ):
        meta = meta if isinstance(meta, dict) else {}
        graded = (
            kind == LearningEvent.TASK_SUBMITTED
            and meta.get("task_type") == "quiz"
            and not meta.get("after_solved")
        )
        rows[user_id].append((stamp, graded, graded and not meta.get("correct")))

    runs = bounded(CodeRun.objects.filter(user_id__in=rows))
    for user_id, stamp, passed, after_solved in runs.values_list(
        "user_id", "created_at", "passed", "after_solved"
    ):
        graded = passed is not None and not after_solved
        rows[user_id].append((stamp, graded, graded and passed is False))
    return rows


def features_from(rows, until, window_days):
    """Base counts and derived features for the ``window_days`` before ``until``."""
    since = until - timedelta(days=window_days)
    week = until - timedelta(days=7)
    inside = [row for row in rows if since <= row[0] < until]
    base = {
        "active_days": len({row[0].date() for row in inside}),
        "events": len(inside),
        "events_last_week": sum(1 for row in inside if row[0] >= week),
        "graded_attempted": sum(1 for row in inside if row[1]),
        "graded_failed": sum(1 for row in inside if row[2]),
    }
    return {**base, **derived(base)}


def derived(base):
    events, attempted = base["events"], base["graded_attempted"]
    return {
        "recent_share": base["events_last_week"] / events if events else 0.0,
        "graded_failed_share": base["graded_failed"] / attempted if attempted else 0.0,
    }


def risk_probabilities(model, user_ids, now):
    """{user_id: probability of leaving} from each learner's recent window."""
    since = now - timedelta(days=model.window_days)
    rows = activity_rows(user_ids, since=since, until=now)
    return {
        user_id: model.probability(features_from(user_rows, now, model.window_days))
        for user_id, user_rows in rows.items()
    }
