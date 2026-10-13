"""Daily snapshots of the early-warning list, and the H3 check built on them.

H3: a learner on the "urgent" list leaves within ``ABANDON_WINDOW_DAYS`` more often than the others. The
list is computed on demand, so the only way to test that later is to write it down every day. Only
learners who agreed to the research are written; the row holds the level, the score and the reason codes.
"""

from datetime import datetime, time, timedelta, timezone as dt_timezone
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from .metrics import ABANDON_WINDOW_DAYS
from .models import CodeRun, EarlyWarningSnapshot, LearningEvent, Progress, TaskProgress
from .stats import clustered_share, cluster_counts
from .warning import assess_students

_OWNER = SimpleNamespace(is_superuser=True)  # the snapshot covers the whole platform
LEVELS = ("high", "medium", "ok")


def take_snapshot(*, now=None):
    """Write today's list once. Returns the number of rows created (0 if today's list already exists).

    Idempotent: a second run on the same UTC date, or two workers running at once, change nothing.
    Learners who never did anything and are not on the list are left out: there is nothing to measure.
    """
    now = now or timezone.now()
    day = now.astimezone(dt_timezone.utc).date()
    if EarlyWarningSnapshot.objects.filter(date=day).exists():
        return 0
    rows = [
        EarlyWarningSnapshot(
            date=day,
            user_id=a["id"],
            level=a["level"],
            score=a["score"],
            reasons=[reason["code"] for reason in a["reasons"]],
        )
        for a in assess_students(_OWNER, now=now, consented_only=True).values()
        if a["level"] != "ok" or a["last_active"] is not None
    ]
    with transaction.atomic():
        created = EarlyWarningSnapshot.objects.bulk_create(rows, ignore_conflicts=True)
    return len(created)


def _active_ids(user_ids, start, end):
    """Learners with any sign of life in [start, end)."""
    seen = set()
    for model, field in (
        (LearningEvent, "created_at"),
        (CodeRun, "created_at"),
        (TaskProgress, "last_submitted_at"),
        (Progress, "last_started_at"),
        (Progress, "completed_at"),
    ):
        seen.update(
            model.objects.filter(
                user_id__in=user_ids, **{f"{field}__gte": start, f"{field}__lt": end}
            ).values_list("user_id", flat=True)
        )
    return seen


def _cell(left, rows):
    """One level of the H3 table: ``rows`` are (user_id, date) snapshot rows, ``left`` the ones that left."""
    sizes = cluster_counts(user_id for user_id, _ in rows)
    stats = clustered_share(sum(1 for row in rows if row in left), sizes)
    if stats is None:
        return {"rows": 0, "left": 0, "learners": 0, "share": None, "ci_low": None, "ci_high": None}
    return {
        "rows": stats["n"],
        "left": sum(1 for row in rows if row in left),
        "learners": stats["learners"],
        "share": round(100 * stats["share"], 1),
        "ci_low": round(100 * stats["ci_low"], 1),
        "ci_high": round(100 * stats["ci_high"], 1),
    }


def h3_summary(*, now=None, window_days=ABANDON_WINDOW_DAYS):
    """Share who left within ``window_days`` after being on the list, by level.

    Only snapshots whose whole window is already over are used (the first day after the snapshot day up to
    ``window_days`` days later), and only learners who still agree to the research. A learner "left" if they
    show no sign of life in that window. Several days of one learner are not independent, so the interval
    uses the learner as the cluster (see ``game.stats``). Returns ``{"mature_days", "levels", "all", ...}``.
    """
    now = now or timezone.now()
    today = now.astimezone(dt_timezone.utc).date()
    last_day = today - timedelta(days=window_days + 1)  # day D is complete once D + 1 + window_days <= today
    snapshots = list(
        EarlyWarningSnapshot.objects.filter(date__lte=last_day, user__profile__research_consent=True)
        .values_list("user_id", "date", "level")
    )
    left = set()
    by_date = {}
    for user_id, day, _ in snapshots:
        by_date.setdefault(day, set()).add(user_id)
    for day, ids in by_date.items():
        start = datetime.combine(day + timedelta(days=1), time.min, tzinfo=dt_timezone.utc)
        end = start + timedelta(days=window_days)
        left.update((user_id, day) for user_id in ids - _active_ids(ids, start, end))

    keyed = {level: [] for level in LEVELS}
    everything = []
    for user_id, day, level in snapshots:
        keyed.setdefault(level, []).append((user_id, day))
        everything.append((user_id, day))
    levels = {level: _cell(left, keyed[level]) for level in LEVELS}
    listed = keyed["high"] + keyed["medium"]
    total_left = sum(1 for row in everything if row in left)
    return {
        "window_days": window_days,
        "mature_days": len(by_date),
        "levels": levels,
        "all": _cell(left, everything),
        "listed": _cell(left, listed),
        "recall_listed": (
            round(100 * sum(1 for row in listed if row in left) / total_left, 1) if total_left else None
        ),
    }
