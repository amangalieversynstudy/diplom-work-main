"""Learning-effectiveness metrics (the KPIs of the analytics module).

Definitions (they are also written in ``docs/METRICS.md`` and must stay in sync):

* **Mission Completion Rate (MCR)** - of the learners who started a mission *and
  have a known outcome* (completed it, or are gone), the share who completed it.
* **Mean Attempts to Success (MAS)** - for quiz/code steps, the mean number of
  counted attempts (up to and including the first success) over the learners who
  solved the step. Story steps are not graded, so they have no MAS.
* **Task Drop-out Rate** - of the (learner, step) pairs with a *known outcome*
  (solved, or not solved and the learner has been inactive for ``inactive_days``),
  the share that was dropped. Pairs of learners who are still active have not
  finished their observation window yet: they are censored, counted apart as
  "in progress" and left out of every denominator.
* **Failure streak curve** - for k = 1, 2, ...: among (learner, step) pairs that
  reached k failed attempts in a row and have a known outcome, the share that ended
  in drop-out. The first
  k where that share reaches ``CRITICAL_DROPOUT_SHARE`` is the "critical
  threshold" after which help must be offered.

Everything is computed from data the platform already stores (``Progress``,
``TaskProgress``, ``LearningEvent``, ``CodeRun``), so metrics also work for
history recorded before the footprint existed - just less richly.
"""

from collections import Counter, defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Max
from django.utils import timezone

from .models import CodeRun, LearningEvent, MissionTask, Progress, TaskProgress

GRADED_TYPES = ("quiz", "code")

# One definition of "left" for the dashboard, the pilot report and the H3 outcome: no sign of life for this long.
ABANDON_WINDOW_DAYS = 14
DEFAULT_INACTIVE_DAYS = ABANDON_WINDOW_DAYS  # the dashboard selector may move it; the pilot report may not
MIN_INACTIVE_DAYS = 1
MAX_INACTIVE_DAYS = 60

MAX_FAILURE_STREAK = 8
CRITICAL_DROPOUT_SHARE = 0.7
# A threshold backed by fewer pairs than this is noise, not a finding.
MIN_SAMPLE = 5

TOP_ERRORS = 8

HELP_NONE = "none"
HELP_HINT = "hint"
HELP_AI = "ai"
# The free "rescue" hint after repeated failures is help like any other: leaving it out would file the
# learners who needed it most under "no help" and make that group look worse than it is.
_HINT_EVENTS = (LearningEvent.HINT_USED, LearningEvent.SKELETON_USED, LearningEvent.HELP_RESCUE)
_AI_EVENTS = (LearningEvent.AI_HINT_USED, LearningEvent.AI_MENTOR_USED)


def clamp_inactive_days(value):
    """Parse the ``inactive_days`` query parameter into a safe integer."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INACTIVE_DAYS
    return max(MIN_INACTIVE_DAYS, min(MAX_INACTIVE_DAYS, days))


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def _mean(values):
    values = list(values)
    return round(sum(values) / len(values), 2) if values else None


def _title(obj):
    return obj.title_ru or obj.title or obj.title_en or f"#{obj.pk}"


def scoped_tasks(viewer, track_id=None):
    """Tasks the viewer may analyse: a teacher's own courses, or all for a superuser."""
    tasks = MissionTask.objects.filter(mission__is_active=True).select_related(
        "mission", "mission__location"
    )
    if not viewer.is_superuser:
        tasks = tasks.filter(mission__location__track__owner=viewer)
    if track_id is not None:
        tasks = tasks.filter(mission__location__track_id=track_id)
    return tasks.order_by(
        "mission__location__track__order", "mission__location__order", "mission__order", "order", "id"
    )


def _last_activity(learner_ids):
    """{user_id: datetime of the learner's most recent sign of life}."""
    latest = {}

    def merge(rows, *fields):
        for row in rows:
            for field in fields:
                stamp = row.get(field)
                if stamp and (row["user_id"] not in latest or stamp > latest[row["user_id"]]):
                    latest[row["user_id"]] = stamp

    merge(
        LearningEvent.objects.filter(user_id__in=learner_ids)
        .values("user_id")
        .annotate(last=Max("created_at")),
        "last",
    )
    merge(
        CodeRun.objects.filter(user_id__in=learner_ids)
        .values("user_id")
        .annotate(last=Max("created_at")),
        "last",
    )
    merge(
        Progress.objects.filter(user_id__in=learner_ids)
        .values("user_id")
        .annotate(started=Max("last_started_at"), done=Max("completed_at")),
        "started",
        "done",
    )
    merge(
        TaskProgress.objects.filter(user_id__in=learner_ids)
        .values("user_id")
        .annotate(last=Max("last_submitted_at")),
        "last",
    )
    return latest


def _help_by_pair(task_ids, learner_ids):
    """({(user_id, task_id): HELP_HINT | HELP_AI} for pairs that used any help, pairs that took the free rescue hint)."""
    used = {}
    rescued = set()
    rows = LearningEvent.objects.filter(
        task_id__in=task_ids,
        user_id__in=learner_ids,
        event_type__in=_HINT_EVENTS + _AI_EVENTS,
    ).values_list("user_id", "task_id", "event_type")
    for user_id, task_id, event_type in rows:
        key = (user_id, task_id)
        if event_type in _AI_EVENTS:
            used[key] = HELP_AI
        else:
            used.setdefault(key, HELP_HINT)
        if event_type == LearningEvent.HELP_RESCUE:
            rescued.add(key)
    return used, rescued


def _opened_pairs(task_ids, students, progress_rows):
    """(user_id, task_id) pairs where the learner opened or tried the step."""
    pairs = {(row["user_id"], row["task_id"]) for row in progress_rows}
    pairs.update(
        LearningEvent.objects.filter(
            event_type=LearningEvent.TASK_OPENED,
            task_id__in=task_ids,
            user__in=students,
        )
        .values_list("user_id", "task_id")
        .distinct()
    )
    pairs.update(
        CodeRun.objects.filter(task_id__in=task_ids, user__in=students)
        .values_list("user_id", "task_id")
        .distinct()
    )
    return pairs


def _failure_curve(graded_pairs, dropped_pairs):
    """Drop-out share by number of failed attempts in a row.

    ``graded_pairs`` maps a pair to ``(failures, solved)``. Failures before the
    first success are consecutive by construction: a success ends the streak.
    Unsolved pairs of learners who are still active have no outcome yet
    (``in_progress``); the share is taken over the pairs with a known outcome.
    """
    curve = []
    for k in range(1, MAX_FAILURE_STREAK + 1):
        reached = [pair for pair, (fails, _) in graded_pairs.items() if fails >= k]
        unsolved = [pair for pair in reached if not graded_pairs[pair][1]]
        dropped = [pair for pair in unsolved if pair in dropped_pairs]
        in_progress = len(unsolved) - len(dropped)
        known = len(reached) - in_progress
        curve.append(
            {
                "failures": k,
                "reached": len(reached),
                "unsolved": len(unsolved),
                "dropped": len(dropped),
                "in_progress": in_progress,
                "known": known,
                "dropout_rate": _pct(len(dropped), known),
            }
        )
    return curve


def _critical_threshold(curve):
    """First streak length whose drop-out share reaches the critical level."""
    for point in curve:
        if point.get("known", point["reached"]) < MIN_SAMPLE or point["dropout_rate"] is None:
            continue
        if point["dropout_rate"] >= 100 * CRITICAL_DROPOUT_SHARE:
            return point["failures"]
    return None


def compute_metrics(
    viewer, *, track_id=None, inactive_days=DEFAULT_INACTIVE_DAYS, now=None, consented_only=False
):
    """All dashboard metrics for the tasks the viewer may see.

    ``consented_only`` leaves out learners who did not agree to the research (the pilot report).
    """
    now = now or timezone.now()
    cutoff = now - timedelta(days=inactive_days)
    User = get_user_model()

    tasks = list(scoped_tasks(viewer, track_id))
    task_ids = [task.pk for task in tasks]
    mission_ids = sorted({task.mission_id for task in tasks})
    students = User.objects.filter(is_staff=False)
    if consented_only:
        students = students.filter(profile__research_consent=True)

    progress_rows = list(
        TaskProgress.objects.filter(task_id__in=task_ids, user__in=students).values(
            "user_id", "task_id", "status", "attempts"
        )
    )
    mission_rows = list(
        Progress.objects.filter(mission_id__in=mission_ids, user__in=students)
        .exclude(started_at__isnull=True)
        .values("mission_id", "user_id", "completed")
    )

    learner_ids = {row["user_id"] for row in progress_rows} | {
        row["user_id"] for row in mission_rows
    }
    opened = _opened_pairs(task_ids, students, progress_rows)
    learner_ids |= {user_id for user_id, _ in opened}
    last_seen = _last_activity(learner_ids)
    inactive = {
        user_id for user_id in learner_ids if last_seen.get(user_id, now - timedelta(days=3650)) < cutoff
    }

    solved = {
        (row["user_id"], row["task_id"]) for row in progress_rows if row["status"] == "completed"
    }
    attempts = {(row["user_id"], row["task_id"]): row["attempts"] for row in progress_rows}
    dropped = {pair for pair in opened - solved if pair[0] in inactive}
    help_used, rescued_pairs = _help_by_pair(task_ids, learner_ids)

    by_task = defaultdict(lambda: {"opened": 0, "solved": 0, "dropped": 0, "helped": 0, "tries": []})
    for pair in opened:
        stats = by_task[pair[1]]
        stats["opened"] += 1
        stats["solved"] += pair in solved
        stats["dropped"] += pair in dropped
        stats["helped"] += pair in help_used
    task_by_id = {task.pk: task for task in tasks}
    graded_pairs = {}
    for pair in opened:
        task = task_by_id.get(pair[1])
        if task is None or task.task_type not in GRADED_TYPES or not attempts.get(pair):
            continue
        is_solved = pair in solved
        # Guessing among four options fails differently from debugging code: explain questions stay
        # out of the failure curve, the overall MAS and the help effect (their own funnel row has them).
        if task.kind != "explain":
            graded_pairs[pair] = (attempts[pair] - 1 if is_solved else attempts[pair], is_solved)
        if is_solved:
            by_task[pair[1]]["tries"].append(attempts[pair])

    error_runs = (
        CodeRun.objects.filter(task_id__in=task_ids, user__in=students)
        .exclude(error_type="")
        .exclude(outcome="runner_error")
    )
    errors_by_task = defaultdict(Counter)
    for row in error_runs.values("task_id", "error_type").annotate(runs=Count("id")):
        errors_by_task[row["task_id"]][row["error_type"]] += row["runs"]
    error_totals = list(
        error_runs.values("error_type")
        .annotate(runs=Count("id"), learners=Count("user_id", distinct=True))
        .order_by("-runs", "error_type")[:TOP_ERRORS]
    )

    task_table = []
    for task in tasks:
        stats = by_task[task.pk]
        top_error = errors_by_task[task.pk].most_common(1)
        task_table.append(
            {
                "task_id": task.pk,
                "mission_id": task.mission_id,
                "mission_title": _title(task.mission),
                "order": task.order,
                "task_type": task.kind,
                "title": _title(task) if task.title or task.title_ru or task.title_en else "",
                "opened": stats["opened"],
                "solved": stats["solved"],
                "solve_rate": _pct(stats["solved"], stats["opened"]),
                "mas": _mean(stats["tries"]),
                "dropped": stats["dropped"],
                # unsolved but the learner is still active: no outcome yet, kept out of the denominator
                "in_progress": stats["opened"] - stats["solved"] - stats["dropped"],
                "known": stats["solved"] + stats["dropped"],
                "dropout_rate": _pct(stats["dropped"], stats["solved"] + stats["dropped"]),
                "help_rate": _pct(stats["helped"], stats["opened"]),
                "top_error": top_error[0][0] if top_error else "",
            }
        )

    # ── mission level ───────────────────────────────────────────────────────
    by_mission = defaultdict(lambda: {"started": 0, "completed": 0, "abandoned": 0})
    for row in mission_rows:
        by_mission[row["mission_id"]]["started"] += 1
        by_mission[row["mission_id"]]["completed"] += bool(row["completed"])
        # not finished and the learner is gone: a known failure; not finished but active: still going
        by_mission[row["mission_id"]]["abandoned"] += not row["completed"] and row["user_id"] in inactive
    mission_titles = {}
    for task in tasks:
        mission_titles.setdefault(task.mission_id, _title(task.mission))
    missions = [
        {
            "mission_id": mission_id,
            "title": mission_titles[mission_id],
            "started": by_mission[mission_id]["started"],
            "completed": by_mission[mission_id]["completed"],
            "in_progress": by_mission[mission_id]["started"]
            - by_mission[mission_id]["completed"]
            - by_mission[mission_id]["abandoned"],
            "completion_rate": _pct(
                by_mission[mission_id]["completed"],
                by_mission[mission_id]["completed"] + by_mission[mission_id]["abandoned"],
            ),
        }
        for mission_id in mission_ids
    ]
    started_total = sum(m["started"] for m in missions)
    completed_total = sum(m["completed"] for m in missions)
    missions_in_progress = sum(m["in_progress"] for m in missions)

    # ── by step type (the Story -> Quiz -> Code funnel) ─────────────────────
    funnel = []
    for task_type in ("story", "quiz", "code", "explain"):
        rows = [row for row in task_table if row["task_type"] == task_type]
        opened_n = sum(row["opened"] for row in rows)
        funnel.append(
            {
                "task_type": task_type,
                "steps": len(rows),
                "opened": opened_n,
                "solved": sum(row["solved"] for row in rows),
                "dropped": sum(row["dropped"] for row in rows),
                "in_progress": sum(row["in_progress"] for row in rows),
                "dropout_rate": _pct(
                    sum(row["dropped"] for row in rows), sum(row["known"] for row in rows)
                ),
                "mas": _mean(
                    tries
                    for task in tasks
                    if task.kind == task_type
                    for tries in by_task[task.pk]["tries"]
                ),
            }
        )

    # ── help effect (descriptive, not causal) ───────────────────────────────
    groups = {HELP_NONE: [], HELP_HINT: [], HELP_AI: []}
    for pair in graded_pairs:
        groups[help_used.get(pair, HELP_NONE)].append(pair)
    help_effect = []
    for name, pairs in groups.items():
        solved_pairs = [pair for pair in pairs if pair in solved]
        gone = sum(pair in dropped for pair in pairs)
        help_effect.append(
            {
                "group": name,
                "pairs": len(pairs),
                "rescued": sum(pair in rescued_pairs for pair in pairs),  # of them, took the free rescue hint
                "solved": len(solved_pairs),
                "solve_rate": _pct(len(solved_pairs), len(pairs)),
                "mas": _mean(attempts[pair] for pair in solved_pairs),
                "in_progress": len(pairs) - len(solved_pairs) - gone,
                "dropout_rate": _pct(gone, len(solved_pairs) + gone),
            }
        )

    curve = _failure_curve(graded_pairs, dropped)
    solved_graded = [attempts[pair] for pair, (_, ok) in graded_pairs.items() if ok]

    return {
        "meta": {
            "generated_at": now.isoformat(),
            "inactive_days": inactive_days,
            "scope": "all" if viewer.is_superuser else "own",
            "track": track_id,
            "learners": len(learner_ids),
            "critical_share": int(100 * CRITICAL_DROPOUT_SHARE),
            "min_sample": MIN_SAMPLE,
        },
        "kpi": {
            "mission_completion_rate": _pct(completed_total, started_total - missions_in_progress),
            "missions_started": started_total,
            "missions_completed": completed_total,
            "missions_in_progress": missions_in_progress,
            "mean_attempts_to_success": _mean(solved_graded),
            "task_dropout_rate": _pct(len(dropped), len(solved & opened) + len(dropped)),
            "steps_opened": len(opened),
            "steps_dropped": len(dropped),
            "steps_in_progress": len(opened) - len(solved & opened) - len(dropped),
            "steps_known": len(solved & opened) + len(dropped),
        },
        "missions": missions,
        "funnel": funnel,
        "tasks": task_table,
        "failure_curve": curve,
        "critical_threshold": _critical_threshold(curve),
        "help_effect": help_effect,
        "top_errors": [
            {"error_type": row["error_type"], "runs": row["runs"], "learners": row["learners"]}
            for row in error_totals
        ],
    }


CSV_COLUMNS = (
    "mission_id",
    "mission_title",
    "task_id",
    "order",
    "task_type",
    "opened",
    "solved",
    "solve_rate",
    "mas",
    "dropped",
    "in_progress",
    "dropout_rate",
    "help_rate",
    "top_error",
)
