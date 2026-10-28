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
from django.db.models import Count, Max, Q
from django.utils import timezone

from .classes import MISSION_TRACK, TASK_TRACK, owner_scope, visible_events, visible_learners, visible_work
from .models import CodeRun, LearningEvent, MissionTask, Progress, TaskProgress
from .stats import clustered_share

GRADED_TYPES = ("quiz", "code")

# One definition of "left" for the dashboard, the pilot report and the H3 outcome: no sign of life for this long.
ABANDON_WINDOW_DAYS = 14
DEFAULT_INACTIVE_DAYS = ABANDON_WINDOW_DAYS  # the dashboard selector may move it; the pilot report may not
MIN_INACTIVE_DAYS = 1
MAX_INACTIVE_DAYS = 60

MAX_FAILURE_STREAK = 8
CRITICAL_DROPOUT_SHARE = 0.7
# A cell or a cohort average backed by fewer learners than this is not shown as a number.
MIN_SAMPLE = 5
# The failure curve and its critical threshold (H1) need more: fewer known pairs, or pairs from fewer
# learners, than this and the dashboard says "too little data" instead of a conclusion.
MIN_CURVE_PAIRS = 20
MIN_CURVE_LEARNERS = 10

TOP_ERRORS = 8
MEDIAN_SOLVE_MIN_RUNS = 3  # fewer solving runs give no median of the time on a step
# Class activity by day for the dashboard chart.
DAILY_DAYS = 14

# Composite learning performance score (вариант «в»): 50% steps + 30% mission stars + 20% explain steps.
PERF_WEIGHT_STEPS = 0.50
PERF_WEIGHT_STARS = 0.30
PERF_WEIGHT_EXPLAIN = 0.20
MAX_STARS_PER_MISSION = 3
PERF_HIGH_THRESHOLD = 70.0
PERF_MEDIUM_THRESHOLD = 40.0

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


def _median_1(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    mid = len(values) // 2
    med = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
    return round(med, 1)


def performance_score_from_counts(
    *,
    steps_done,
    steps_total,
    stars_earned,
    missions_total,
    explain_done,
    explain_total,
):
    """Composite learning performance score on a 0..100 scale (вариант «в»).

    Fixed dissertation formula:
        S = 0.50 * (steps_done / steps_total)
          + 0.30 * (stars_earned / (3 * missions_total))
          + 0.20 * (explain_done / explain_total)   [in %]

    When a course has no ``explain`` steps (or no missions), the active components
    with positive denominators are re-normalised by their weight sum so the scale
    stays 0..100.
    """
    max_stars = MAX_STARS_PER_MISSION * max(0, int(missions_total or 0))
    clamped_stars = min(max_stars, max(0, int(stars_earned or 0)))
    steps_done = max(0, int(steps_done or 0))
    steps_total = max(0, int(steps_total or 0))
    explain_done = max(0, int(explain_done or 0))
    explain_total = max(0, int(explain_total or 0))

    steps_share = _pct(min(steps_total, steps_done), steps_total)
    stars_share = _pct(clamped_stars, max_stars)
    explain_share = _pct(min(explain_total, explain_done), explain_total)

    weighted_sum = 0.0
    weight_total = 0.0
    if steps_total > 0:
        weighted_sum += PERF_WEIGHT_STEPS * (100.0 * min(steps_total, steps_done) / steps_total)
        weight_total += PERF_WEIGHT_STEPS
    if max_stars > 0:
        weighted_sum += PERF_WEIGHT_STARS * (100.0 * clamped_stars / max_stars)
        weight_total += PERF_WEIGHT_STARS
    if explain_total > 0:
        weighted_sum += PERF_WEIGHT_EXPLAIN * (100.0 * min(explain_total, explain_done) / explain_total)
        weight_total += PERF_WEIGHT_EXPLAIN

    score = round(weighted_sum / weight_total, 1) if weight_total > 0 else None
    return {
        "score": score,
        "steps_share": steps_share,
        "stars_share": stars_share,
        "explain_share": explain_share,
        "steps_done": min(steps_total, steps_done),
        "steps_total": steps_total,
        "stars_earned": clamped_stars,
        "stars_max": max_stars,
        "explain_done": min(explain_total, explain_done),
        "explain_total": explain_total,
        "weights": {
            "steps": int(round(100 * PERF_WEIGHT_STEPS)),
            "stars": int(round(100 * PERF_WEIGHT_STARS)),
            "explain": int(round(100 * PERF_WEIGHT_EXPLAIN)),
        },
    }


def _cohort_performance(tasks, mission_ids, learner_ids, solved_pairs, mission_rows):
    """Per-learner and cohort composite performance summary for ``compute_metrics``."""
    steps_total = len(tasks)
    missions_total = len(mission_ids)
    explain_ids = {task.pk for task in tasks if task.kind == "explain"}
    explain_total = len(explain_ids)

    solved_by_user = defaultdict(int)
    explain_by_user = defaultdict(int)
    for user_id, task_id in solved_pairs:
        solved_by_user[user_id] += 1
        if task_id in explain_ids:
            explain_by_user[user_id] += 1

    stars_by_user = defaultdict(int)
    for row in mission_rows:
        stars = min(MAX_STARS_PER_MISSION, max(0, int(row.get("stars") or 0)))
        stars_by_user[row["user_id"]] += stars

    per_learner = {}
    for user_id in sorted(learner_ids):
        per_learner[user_id] = performance_score_from_counts(
            steps_done=solved_by_user[user_id],
            steps_total=steps_total,
            stars_earned=stars_by_user[user_id],
            missions_total=missions_total,
            explain_done=explain_by_user[user_id],
            explain_total=explain_total,
        )

    scores = [p["score"] for p in per_learner.values() if p["score"] is not None]
    steps_shares = [p["steps_share"] for p in per_learner.values() if p["steps_share"] is not None]
    stars_shares = [p["stars_share"] for p in per_learner.values() if p["stars_share"] is not None]
    explain_shares = [p["explain_share"] for p in per_learner.values() if p["explain_share"] is not None]

    return {
        "mean_score": round(sum(scores) / len(scores), 1) if scores else None,
        "median_score": _median_1(scores),
        "learners": len(scores),
        "steps_share": round(sum(steps_shares) / len(steps_shares), 1) if steps_shares else None,
        "stars_share": round(sum(stars_shares) / len(stars_shares), 1) if stars_shares else None,
        "explain_share": round(sum(explain_shares) / len(explain_shares), 1) if explain_shares else None,
        "steps_total": steps_total,
        "missions_total": missions_total,
        "stars_max": MAX_STARS_PER_MISSION * missions_total,
        "explain_total": explain_total,
        "weights": {
            "steps": int(round(100 * PERF_WEIGHT_STEPS)),
            "stars": int(round(100 * PERF_WEIGHT_STARS)),
            "explain": int(round(100 * PERF_WEIGHT_EXPLAIN)),
        },
        "tiers": {
            "high": sum(1 for s in scores if s >= PERF_HIGH_THRESHOLD),
            "medium": sum(1 for s in scores if PERF_MEDIUM_THRESHOLD <= s < PERF_HIGH_THRESHOLD),
            "low": sum(1 for s in scores if s < PERF_MEDIUM_THRESHOLD),
        },
        "by_learner": per_learner,
    }


def _title(obj):
    return obj.title_ru or obj.title or obj.title_en or f"#{obj.pk}"


def student_performance_map(viewer, learner_ids):
    """{user_id: performance_dict} for learners in ``viewer``'s scope."""
    if not learner_ids:
        return {}
    tasks = list(scoped_tasks(viewer))
    task_ids = [t.pk for t in tasks]
    mission_ids = sorted({t.mission_id for t in tasks})
    work = visible_work(viewer, TASK_TRACK)
    solved = set(
        TaskProgress.objects.filter(
            task_id__in=task_ids, user_id__in=learner_ids, status="completed"
        )
        .filter(work)
        .values_list("user_id", "task_id")
    )
    mission_rows = list(
        Progress.objects.filter(mission_id__in=mission_ids, user_id__in=learner_ids)
        .filter(visible_work(viewer, MISSION_TRACK))
        .values("mission_id", "user_id", "completed", "stars")
    )
    return _cohort_performance(tasks, mission_ids, learner_ids, solved, mission_rows)["by_learner"]


def pilot_content_q(track_path):
    """Content the pilot's numbers may come from: public courses, track-less content, and classes of teachers the
    platform vouched for (superuser, or staff that is not a self-service teacher). A self-service teacher's class,
    with any accounts it invites, cannot reach the dissertation figures."""
    return (
        Q(**{f"{track_path}__isnull": True})
        | Q(**{f"{track_path}__is_public": True})
        | Q(**{f"{track_path}__owner__is_superuser": True})
        | Q(**{f"{track_path}__owner__is_staff": True, f"{track_path}__owner__is_teacher": False})
    )


def scoped_tasks(viewer, track_id=None):
    """Tasks the viewer may analyse: a teacher's own courses, or all for a superuser.

    The pilot report and snapshots pass a stand-in with ``pilot_only``: every course, but only pilot content.
    """
    tasks = MissionTask.objects.filter(mission__is_active=True).select_related(
        "mission", "mission__location"
    )
    if not viewer.is_superuser:
        tasks = tasks.filter(mission__location__track__owner=viewer)
    if getattr(viewer, "pilot_only", False):
        tasks = tasks.filter(pilot_content_q("mission__location__track"))
    if track_id is not None:
        tasks = tasks.filter(mission__location__track_id=track_id)
    return tasks.order_by(
        "mission__location__track__order", "mission__location__order", "mission__order", "order", "id"
    )


def _last_activity(learner_ids, owner=None):
    """{user_id: datetime of the learner's most recent sign of life}.

    Without ``owner``: anywhere on the platform (the definition of "left" in the pilot report and H3). With an
    ``owner`` (a teacher who is not a superuser): only work in that teacher's courses, and in a closed course only
    while the learner is enrolled, so logins, free practice and other teachers' classes stay private.
    """
    latest = {}
    events = LearningEvent.objects.filter(user_id__in=learner_ids)
    runs = CodeRun.objects.filter(user_id__in=learner_ids)
    missions = Progress.objects.filter(user_id__in=learner_ids)
    steps = TaskProgress.objects.filter(user_id__in=learner_ids)
    if owner is not None:
        events = events.filter(visible_events(owner))
        runs = runs.filter(visible_work(owner, TASK_TRACK))
        missions = missions.filter(visible_work(owner, MISSION_TRACK))
        steps = steps.filter(visible_work(owner, TASK_TRACK))

    def merge(rows, *fields):
        for row in rows:
            for field in fields:
                stamp = row.get(field)
                if stamp and (row["user_id"] not in latest or stamp > latest[row["user_id"]]):
                    latest[row["user_id"]] = stamp

    merge(events.values("user_id").annotate(last=Max("created_at")).order_by(), "last")
    merge(runs.values("user_id").annotate(last=Max("created_at")).order_by(), "last")
    merge(
        missions.values("user_id").annotate(started=Max("last_started_at"), done=Max("completed_at")).order_by(),
        "started",
        "done",
    )
    merge(steps.values("user_id").annotate(last=Max("last_submitted_at")).order_by(), "last")
    return latest


def _daily_activity(task_ids, mission_ids, learner_ids, now, days=DAILY_DAYS, *, work=Q(), events=Q()):
    """Per day of the last ``days``: learners who did anything, steps solved, code runs (the class trend).

    Only work in the viewer's own courses counts; free-practice runs belong to no course and stay out.
    Days are UTC dates, like every other day-level figure here.
    """
    today = now.date()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    since = now - timedelta(days=days)
    active = {day: set() for day in dates}
    solved = {day: 0 for day in dates}
    runs = {day: 0 for day in dates}
    learners = list(learner_ids)

    for user_id, stamp in CodeRun.objects.filter(
        user_id__in=learners, task_id__in=task_ids, created_at__gte=since
    ).filter(work).values_list("user_id", "created_at"):
        if stamp.date() in runs:
            runs[stamp.date()] += 1
            active[stamp.date()].add(user_id)
    for user_id, stamp in LearningEvent.objects.filter(
        Q(task_id__in=task_ids) | Q(mission_id__in=mission_ids),
        user_id__in=learners,
        created_at__gte=since,
    ).filter(events).values_list("user_id", "created_at"):
        if stamp.date() in active:
            active[stamp.date()].add(user_id)
    for user_id, stamp, status in TaskProgress.objects.filter(
        user_id__in=learners, task_id__in=task_ids, last_submitted_at__gte=since
    ).filter(work).values_list("user_id", "last_submitted_at", "status"):
        if stamp.date() in active:
            active[stamp.date()].add(user_id)
            solved[stamp.date()] += status == "completed"
    return [
        {"date": day.isoformat(), "active": len(active[day]), "solved": solved[day], "runs": runs[day]}
        for day in dates
    ]


def _help_by_pair(task_ids, learner_ids, work=Q()):
    """({(user_id, task_id): HELP_HINT | HELP_AI} for pairs that used any help, pairs that took the free rescue hint)."""
    used = {}
    rescued = set()
    rows = LearningEvent.objects.filter(
        task_id__in=task_ids,
        user_id__in=learner_ids,
        event_type__in=_HINT_EVENTS + _AI_EVENTS,
    ).filter(work).values_list("user_id", "task_id", "event_type")
    for user_id, task_id, event_type in rows:
        key = (user_id, task_id)
        if event_type in _AI_EVENTS:
            used[key] = HELP_AI
        else:
            used.setdefault(key, HELP_HINT)
        if event_type == LearningEvent.HELP_RESCUE:
            rescued.add(key)
    return used, rescued


def _opened_pairs(task_ids, students, progress_rows, work=Q()):
    """(user_id, task_id) pairs where the learner opened or tried the step."""
    pairs = {(row["user_id"], row["task_id"]) for row in progress_rows}
    pairs.update(
        LearningEvent.objects.filter(
            event_type=LearningEvent.TASK_OPENED,
            task_id__in=task_ids,
            user__in=students,
        )
        .filter(work)
        .values_list("user_id", "task_id")
        .distinct()
    )
    pairs.update(
        CodeRun.objects.filter(task_id__in=task_ids, user__in=students)
        .filter(work)
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
    Pairs of one learner are not independent (if they leave, all their open pairs "leave"),
    so the 95% interval is computed with the learner as the cluster (``game.stats``).
    """
    curve = []
    for k in range(1, MAX_FAILURE_STREAK + 1):
        reached = [pair for pair, (fails, _) in graded_pairs.items() if fails >= k]
        unsolved = [pair for pair in reached if not graded_pairs[pair][1]]
        dropped = [pair for pair in unsolved if pair in dropped_pairs]
        in_progress = len(unsolved) - len(dropped)
        known = len(reached) - in_progress
        waiting = {pair for pair in unsolved if pair not in dropped_pairs}
        sizes = Counter(pair[0] for pair in reached if pair not in waiting)
        stats = clustered_share(len(dropped), sizes)
        curve.append(
            {
                "failures": k,
                "reached": len(reached),
                "unsolved": len(unsolved),
                "dropped": len(dropped),
                "in_progress": in_progress,
                "known": known,
                "learners": len(sizes),
                "dropout_rate": _pct(len(dropped), known),
                "ci_low": round(100 * stats["ci_low"], 1) if stats else None,
                "ci_high": round(100 * stats["ci_high"], 1) if stats else None,
                "enough": known >= MIN_CURVE_PAIRS and len(sizes) >= MIN_CURVE_LEARNERS,
            }
        )
    return curve


def _enough(point):
    """Is the point backed by enough known pairs from enough learners to say anything?"""
    return (
        point.get("known", point["reached"]) >= MIN_CURVE_PAIRS
        and point.get("learners", MIN_CURVE_LEARNERS) >= MIN_CURVE_LEARNERS
    )


def _critical_threshold(curve):
    """First streak length whose drop-out share reaches the critical level (with enough data)."""
    for point in curve:
        if not _enough(point) or point["dropout_rate"] is None:
            continue
        if point["dropout_rate"] >= 100 * CRITICAL_DROPOUT_SHARE:
            return point["failures"]
    return None


def _threshold_status(curve, threshold):
    """``found``, ``none`` (enough data, no such point) or ``too_few`` (nothing to conclude from)."""
    if threshold is not None:
        return "found"
    return "none" if any(_enough(point) for point in curve) else "too_few"


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
    # only learners this viewer may see: their classes and their public courses (never a learner who merely
    # wandered into a closed course, or who left the class)
    students = visible_learners(viewer)
    if consented_only:
        students = students.filter(profile__research_consent=True)

    # rows of a closed course count only while their learner is enrolled; Q() for a superuser
    work = visible_work(viewer, TASK_TRACK)
    progress_rows = list(
        TaskProgress.objects.filter(task_id__in=task_ids, user__in=students).filter(work).values(
            "user_id", "task_id", "status", "attempts"
        )
    )
    mission_rows = list(
        Progress.objects.filter(mission_id__in=mission_ids, user__in=students)
        .filter(visible_work(viewer, MISSION_TRACK))
        .exclude(started_at__isnull=True)
        .values("mission_id", "user_id", "completed", "stars")
    )

    learner_ids = {row["user_id"] for row in progress_rows} | {
        row["user_id"] for row in mission_rows
    }
    opened = _opened_pairs(task_ids, students, progress_rows, work)
    learner_ids |= {user_id for user_id, _ in opened}
    # a teacher's "left" means no work in the teacher's own courses; the platform-wide definition is kept for a
    # superuser and therefore for the pilot report and H3 (they run as a superuser stand-in)
    last_seen = _last_activity(learner_ids, owner=owner_scope(viewer))
    inactive = {
        user_id for user_id in learner_ids if last_seen.get(user_id, now - timedelta(days=3650)) < cutoff
    }

    solved = {
        (row["user_id"], row["task_id"]) for row in progress_rows if row["status"] == "completed"
    }
    attempts = {(row["user_id"], row["task_id"]): row["attempts"] for row in progress_rows}
    dropped = {pair for pair in opened - solved if pair[0] in inactive}
    help_used, rescued_pairs = _help_by_pair(task_ids, learner_ids, work)

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
        .filter(work)
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

    # time on step (R6): seconds of the solving run (first passed run per learner), active time when sent
    solve_seconds = defaultdict(dict)
    for run in (
        CodeRun.objects.filter(task_id__in=task_ids, user__in=students, passed=True, after_solved=False)
        .filter(work)
        .order_by("created_at")
        .only("task_id", "user_id", "provenance")
    ):
        if run.user_id in solve_seconds[run.task_id]:
            continue
        data = run.provenance or {}
        ms = data.get("active_ms") or data.get("elapsed_ms") or 0
        solve_seconds[run.task_id][run.user_id] = ms / 1000 if ms else None

    def _median_solve(task_id):
        values = sorted(v for v in solve_seconds[task_id].values() if v is not None)
        if len(values) < MEDIAN_SOLVE_MIN_RUNS:
            return None, len(values)
        mid = len(values) // 2
        median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
        return int(round(median)), len(values)

    task_table = []
    for task in tasks:
        stats = by_task[task.pk]
        median_s, median_n = _median_solve(task.pk)
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
                "median_solve_s": median_s,
                "median_solve_n": median_n,
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

    from .warning import INACTIVE_LONG_DAYS  # warning imports this module, so import late

    curve = _failure_curve(graded_pairs, dropped)
    threshold = _critical_threshold(curve)
    critical_point = next((p for p in curve if p["failures"] == threshold), None)
    solved_graded = [attempts[pair] for pair, (_, ok) in graded_pairs.items() if ok]
    cohort_perf = _cohort_performance(tasks, mission_ids, learner_ids, solved, mission_rows)
    from .patterns import compute_behavioral_patterns

    perf_summary = {k: v for k, v in cohort_perf.items() if k != "by_learner"}
    graded_task_ids = [t.id for t in tasks if t.task_type in GRADED_TYPES]
    behavioral_patterns = compute_behavioral_patterns(
        viewer,
        track_id=track_id,
        learner_ids=list(learner_ids),
        task_ids=graded_task_ids,
        performance_by_user={
            uid: p["score"] for uid, p in cohort_perf.get("by_learner", {}).items()
        },
    )

    return {
        "meta": {
            "generated_at": now.isoformat(),
            "inactive_days": inactive_days,
            "risk_days": INACTIVE_LONG_DAYS,
            "scope": "all" if viewer.is_superuser else "own",
            # where "left" is measured: the whole platform, or only the teacher's own courses
            "activity_scope": "platform" if viewer.is_superuser else "own_courses",
            "track": track_id,
            "learners": len(learner_ids),
            "critical_share": int(100 * CRITICAL_DROPOUT_SHARE),
            "min_sample": MIN_SAMPLE,
            "min_curve_pairs": MIN_CURVE_PAIRS,
            "min_curve_learners": MIN_CURVE_LEARNERS,
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
            "performance_score": perf_summary["mean_score"],
            "performance_median": perf_summary["median_score"],
        },
        "performance": perf_summary,
        "behavioral_patterns": behavioral_patterns,
        "missions": missions,
        "daily": _daily_activity(
            task_ids, mission_ids, learner_ids, now, work=work, events=visible_events(viewer)
        ),
        "funnel": funnel,
        "tasks": task_table,
        "failure_curve": curve,
        "critical_threshold": threshold,
        # the point behind the threshold: the estimate and the interval are reported apart, and
        # ``confirmed`` says whether even the lower bound reaches the critical share
        "critical_point": (
            {
                "failures": critical_point["failures"],
                "dropout_rate": critical_point["dropout_rate"],
                "ci_low": critical_point["ci_low"],
                "ci_high": critical_point["ci_high"],
                "known": critical_point["known"],
                "learners": critical_point["learners"],
                "confirmed": critical_point["ci_low"] >= 100 * CRITICAL_DROPOUT_SHARE,
            }
            if critical_point
            else None
        ),
        "threshold_status": _threshold_status(curve, threshold),
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
