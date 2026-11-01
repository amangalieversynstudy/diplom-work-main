"""Daily snapshots of the early-warning list, and the H3 check built on them.

H3: a learner on the "urgent" list leaves within ``ABANDON_WINDOW_DAYS`` more often than the others. The
list is computed on demand, so the only way to test that later is to write it down every day. Only
research participants are written (``cohort.research_learners``); the row holds the level, the score and the
reason codes. Which rows the test may use is decided when it is computed (``h3_summary``), so the raw snapshots
stay complete.
"""

import random
from datetime import datetime, time, timedelta, timezone as dt_timezone
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from .cohort import course_spans, in_course, pilot_period, research_learners
from .metrics import ABANDON_WINDOW_DAYS
from .models import CodeRun, EarlyWarningSnapshot, LearningEvent, Progress, TaskProgress
from .stats import clustered_share, cluster_counts
from .warning import assess_students

# the snapshot covers the whole platform, pilot content only (see metrics.pilot_content_q)
_OWNER = SimpleNamespace(is_superuser=True, pilot_only=True)
LEVELS = ("high", "medium", "ok")


def take_snapshot(*, now=None):
    """Write today's list once. Returns the number of rows created (0 if today's list already exists).

    Idempotent: a second run on the same UTC date, or two workers running at once, change nothing. Nothing is
    written once PILOT_ENDED_AT has passed.
    Learners who never did anything and are not on the list are left out: there is nothing to measure.
    """
    now = now or timezone.now()
    _, end = pilot_period()
    if end is not None and now >= end:
        return 0  # the active period is over: a list now would only record the silence after the course
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


BOOTSTRAP_REPLICATES = 2000
MIN_REPLICATES = 100  # fewer usable replicates than this: no interval


def bootstrap_difference(rows, left, group_a, group_b, *, replicates=BOOTSTRAP_REPLICATES, seed=0):
    """Share who left in group A minus group B, in percentage points, with a 95% interval from a bootstrap that
    resamples learners (all rows of a drawn learner go in, the same draw for both groups: rows of one learner are
    not independent, and one learner can be in both groups on different days).

    ``rows`` is ``{(user_id, day): level}``; ``group_a`` / ``group_b`` are sets of levels.
    """
    per_learner = {}
    for (user_id, day), level in rows.items():
        counts = per_learner.setdefault(user_id, [0, 0, 0, 0])  # a rows, a left, b rows, b left
        gone = (user_id, day) in left
        if level in group_a:
            counts[0] += 1
            counts[1] += gone
        if level in group_b:
            counts[2] += 1
            counts[3] += gone

    def difference(sample):
        a_rows = sum(c[0] for c in sample)
        b_rows = sum(c[2] for c in sample)
        if not a_rows or not b_rows:
            return None
        return 100 * (sum(c[1] for c in sample) / a_rows - sum(c[3] for c in sample) / b_rows)

    learners = list(per_learner.values())
    estimate = difference(learners)
    result = {
        "estimate": None if estimate is None else round(estimate, 1),
        "ci_low": None,
        "ci_high": None,
        "replicates": 0,
        "learners_a": sum(1 for c in learners if c[0]),
        "learners_b": sum(1 for c in learners if c[2]),
    }
    if estimate is None:
        return result
    rng = random.Random(seed)
    draws = []
    for _ in range(replicates):
        value = difference([learners[rng.randrange(len(learners))] for _ in learners])
        if value is not None:
            draws.append(value)
    result["replicates"] = len(draws)
    if len(draws) >= MIN_REPLICATES:
        draws.sort()
        result["ci_low"] = round(draws[int(0.025 * (len(draws) - 1))], 1)
        result["ci_high"] = round(draws[int(0.975 * (len(draws) - 1))], 1)
    return result


def _day_start(day):
    return datetime.combine(day, time.min, tzinfo=dt_timezone.utc)


def h3_summary(*, now=None, window_days=ABANDON_WINDOW_DAYS, contacts=None):
    """Share who left within ``window_days`` after being on the list, by level, plus the pre-registered H3 test.

    A row (learner, snapshot day D) is the forecast made at the start of day D+1 (UTC). It counts only when:

    * the learner is a research participant (``cohort.research_learners``) and D is not before PILOT_STARTED_AT;
    * the whole outcome window, days D+1 .. D+``window_days``, is over and, with PILOT_ENDED_AT, ends inside the
      active period: silence after the course is not leaving;
    * the learner was inside a started, unfinished pilot course at that moment: a finished course is censored,
      not "left";
    * the learner showed a sign of life in the ``window_days`` before it: whoever is already gone is not a
      forecast, the list would only "predict" that the silent stay silent;
    * with ``contacts`` (``{user_id: date}``, the teacher's contact log): D is before the first contact, because
      the teacher's help changes the outcome the list is checked against.

    A learner "left" when they show no sign of life in the outcome window. Several days of one learner are not
    independent, so intervals treat the learner as the cluster (see ``game.stats``) and the main test, the
    difference "urgent minus the rest", is bootstrapped over learners.
    """
    now = now or timezone.now()
    today = now.astimezone(dt_timezone.utc).date()
    last_day = today - timedelta(days=window_days + 1)  # day D is complete once D + 1 + window_days <= today
    start, end = pilot_period()
    window = timedelta(days=window_days)

    snaps = EarlyWarningSnapshot.objects.filter(
        date__lte=last_day, user_id__in=research_learners().values("pk")
    )
    if start is not None:
        snaps = snaps.filter(date__gte=start.astimezone(dt_timezone.utc).date())
    snaps = list(snaps.values_list("user_id", "date", "level", "reasons"))

    excluded = {"after_end": 0, "not_in_course": 0, "already_gone": 0, "after_contact": 0}
    if end is not None:
        inside = [row for row in snaps if _day_start(row[1] + timedelta(days=1)) + window <= end]
        excluded["after_end"] = len(snaps) - len(inside)
        snaps = inside
    spans = course_spans({row[0] for row in snaps})

    by_date = {}
    for user_id, day, _, _ in snaps:
        by_date.setdefault(day, set()).add(user_id)
    recently_active, left = {}, set()
    for day, ids in by_date.items():
        moment = _day_start(day + timedelta(days=1))
        recently_active[day] = _active_ids(ids, moment - window, moment)
        left.update((user_id, day) for user_id in ids - _active_ids(ids, moment, moment + window))

    contacts = contacts or {}
    kept = {}  # (user_id, day) -> level
    reasons_of = {}
    for user_id, day, level, reasons in snaps:
        if contacts.get(user_id) is not None and day >= contacts[user_id]:
            excluded["after_contact"] += 1
        elif not in_course(spans.get(user_id, []), _day_start(day + timedelta(days=1))):
            excluded["not_in_course"] += 1
        elif user_id not in recently_active[day]:
            excluded["already_gone"] += 1
        else:
            kept[(user_id, day)] = level
            reasons_of[(user_id, day)] = set(reasons or [])
    left &= set(kept)

    keyed = {level: [] for level in LEVELS}
    for row, level in kept.items():
        keyed.setdefault(level, []).append(row)
    everything = list(kept)
    listed = keyed["high"] + keyed["medium"]
    total_left = sum(1 for row in everything if row in left)

    # per learner: of those who left at least once, how many had been on the list on or before that day
    first_left = {}
    for user_id, day in sorted(left, key=lambda row: row[1]):
        first_left.setdefault(user_id, day)
    flagged_before = {
        user_id for user_id, day in listed if user_id in first_left and day <= first_left[user_id]
    }
    stuck_rows = [row for row in listed if "stuck_task" in reasons_of[row] and "inactive" not in reasons_of[row]]
    inactive_rows = [row for row in listed if "inactive" in reasons_of[row]]
    return {
        "window_days": window_days,
        "mature_days": len({day for _, day in everything}),
        "levels": {level: _cell(left, keyed[level]) for level in LEVELS},
        "all": _cell(left, everything),
        "listed": _cell(left, listed),
        "recall_listed": (
            round(100 * sum(1 for row in listed if row in left) / total_left, 1) if total_left else None
        ),
        "recall_learners": {
            "left": len(first_left),
            "flagged_before": len(flagged_before),
            "share": round(100 * len(flagged_before) / len(first_left), 1) if first_left else None,
        },
        "by_reason": {"stuck": _cell(left, stuck_rows), "inactive": _cell(left, inactive_rows)},
        "difference_high_ok": bootstrap_difference(kept, left, {"high"}, {"ok"}),
        "difference_listed_ok": bootstrap_difference(kept, left, {"high", "medium"}, {"ok"}),
        "excluded": excluded,
        "period": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
        "contacts": len(contacts),
    }
