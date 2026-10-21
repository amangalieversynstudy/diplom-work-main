"""The learner's own view of their learning ("Мой путь").

The teacher's dashboard answers "where do students get stuck?"; this answers the
same question for one student, kindly: what is going well, what is hard right
now, what to repeat and what to do next. It shows counts and plain-language
statuses, never a risk probability (the model is not calibrated, and a number
like "72% chance you will quit" would do harm).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Max, Sum
from django.utils import timezone

from .classes import MISSION_TRACK, TASK_TRACK, visible_learners, visible_work
from .metrics import MIN_SAMPLE, _last_activity, _mean
from .models import CodeRun, LearningEvent, Mission, MissionTask, Progress, TaskProgress
from .services import HELP_AFTER_FAILURES, only_published
from .warning import INACTIVE_LONG_DAYS

GRADED = ("quiz", "code")
# a solved step that needed this many tries is worth a second look
REVIEW_ATTEMPTS = HELP_AFTER_FAILURES + 1
ACTIVITY_DAYS = 14
LIST_LIMIT = 3

User = get_user_model()


def _pick(obj, lang):
    """Title of a mission or task in the learner's language."""
    return obj.get_localized_title(lang) or obj.title or f"#{obj.pk}"


def _is_explain(task):
    return task.kind == "explain"


def _counts(task):
    """Does this step count for "attempts to success": a quiz or code step, but not an explain question."""
    return task.task_type in GRADED and not _is_explain(task)


def _step_ref(task, lang, attempts=None):
    ref = {
        "task_id": task.pk,
        "mission_id": task.mission_id,
        "title": _pick(task, lang),
        "mission_title": _pick(task.mission, lang),
        "task_type": task.task_type,
    }
    if attempts is not None:
        ref["attempts"] = attempts
    return ref


def _cohort_mean_attempts(exclude_user_id, task_ids=None, users=None):
    """Mean tries-to-success of everyone else, or None when the group is too small
    to show without pointing at individuals.

    One aggregate query. Explain questions stay out (guessing among options is not debugging), and so do
    teacher and staff accounts (their trial runs are not learners' work). In a teacher's view of a student the
    comparison is limited to that teacher's steps (``task_ids``) and the learners the teacher may see
    (``users``)."""
    explain = MissionTask.objects.filter(task_type="quiz", data__kind="explain").values("pk")
    rows = (
        TaskProgress.objects.filter(status="completed", task__task_type__in=GRADED)
        .exclude(task_id__in=explain)
        .exclude(user_id=exclude_user_id)
        .exclude(user__is_staff=True)
        .exclude(user__is_teacher=True)
    )
    if task_ids is not None:
        rows = rows.filter(task_id__in=list(task_ids))
    if users is not None:
        rows = rows.filter(user__in=users)
    agg = rows.aggregate(mean=Avg("attempts"), n=Count("user_id", distinct=True))
    size = agg["n"] or 0
    if size < MIN_SAMPLE or agg["mean"] is None:
        return None, size
    return round(agg["mean"], 2), size


def _next_step(user, missions, tasks_by_mission, solved, completed_missions):
    """The first unsolved step of the first mission the learner can open."""
    level = user.profile.level
    for mission in missions:
        if mission.pk in completed_missions or mission.min_level > level:
            continue
        needed = {pre.pk for pre in mission.prerequisites.all()}
        if needed - completed_missions:
            continue
        for task in tasks_by_mission.get(mission.pk, []):
            if task.pk not in solved:
                return task
    return None


def _status(has_activity, days_away, stuck, mean_attempts, solved_graded):
    if not has_activity:
        return "new"
    if days_away is not None and days_away >= INACTIVE_LONG_DAYS:
        return "away"
    if any(item["attempts"] >= HELP_AFTER_FAILURES for item in stuck):
        return "stuck"
    if solved_graded >= 2 and mean_attempts is not None and mean_attempts <= 1.5:
        return "great"
    return "steady"


def my_learning(user, *, lang="ru", now=None, owner=None):
    """The learner's own picture. ``owner`` limits it to that teacher's courses
    (the teacher's view of a student must not show what happens in other courses)."""
    now = now or timezone.now()
    visible = only_published(Mission.objects.filter(is_active=True), user, "location__track")
    if owner is not None:
        visible = visible.filter(location__track__owner=owner)
    missions = list(
        visible
        .select_related("location", "location__track")
        .prefetch_related("prerequisites")
        .order_by("location__track__order", "location__order", "order", "id")
    )
    mission_ids = [m.pk for m in missions]
    tasks = list(
        MissionTask.objects.filter(mission_id__in=mission_ids)
        .select_related("mission")
        .order_by(
            "mission__location__track__order", "mission__location__order", "mission__order", "order", "id"
        )
    )
    tasks_by_mission = {}
    for task in tasks:
        tasks_by_mission.setdefault(task.mission_id, []).append(task)
    task_by_id = {t.pk: t for t in tasks}

    progress = {
        row.task_id: row
        for row in TaskProgress.objects.filter(user=user, task_id__in=task_by_id)
    }
    solved = {tid for tid, row in progress.items() if row.status == "completed"}
    completed_missions = set(
        Progress.objects.filter(
            user=user, completed=True, mission_id__in=mission_ids
        ).values_list("mission_id", flat=True)
    )

    # what is hard right now / what was hard before
    # the "explain your solution" question does not count as being stuck (and stays out of the averages);
    # it is dropped before the list is cut, or three wrong answers to it would push real trouble out
    stuck = sorted(
        (
            (tid, row.attempts)
            for tid, row in progress.items()
            if row.status != "completed" and row.attempts >= 1 and not _is_explain(task_by_id[tid])
        ),
        key=lambda pair: -pair[1],
    )[:LIST_LIMIT]
    stuck = [_step_ref(task_by_id[tid], lang, attempts) for tid, attempts in stuck]
    review = sorted(
        (
            (tid, row.attempts)
            for tid, row in progress.items()
            if row.status == "completed"
            and _counts(task_by_id[tid])
            and row.attempts >= REVIEW_ATTEMPTS
        ),
        key=lambda pair: -pair[1],
    )[:LIST_LIMIT]
    review = [_step_ref(task_by_id[tid], lang, attempts) for tid, attempts in review]

    solved_graded = [
        progress[tid].attempts for tid in solved if _counts(task_by_id[tid])
    ]
    mean_attempts = _mean(solved_graded)
    first_try = (
        round(100 * sum(1 for a in solved_graded if a <= 1) / len(solved_graded))
        if solved_graded
        else None
    )
    if owner is None:
        cohort_mean, cohort_size = _cohort_mean_attempts(user.pk)
    else:
        cohort_mean, cohort_size = _cohort_mean_attempts(
            user.pk, task_ids=list(task_by_id), users=visible_learners(owner)
        )

    # a teacher sees only work in their own courses (a closed one while the learner is enrolled)
    last_seen = _last_activity([user.pk], owner=owner).get(user.pk)
    days_away = (now - last_seen).days if last_seen else None
    has_activity = bool(progress) or last_seen is not None

    # last two weeks: runs and solved steps per day
    today = now.date()
    days = [today - timedelta(days=offset) for offset in range(ACTIVITY_DAYS - 1, -1, -1)]
    since = now - timedelta(days=ACTIVITY_DAYS)
    runs = {day: 0 for day in days}
    run_rows = CodeRun.objects.filter(user=user, created_at__gte=since)
    solved_rows = TaskProgress.objects.filter(
        user=user, status="completed", last_submitted_at__gte=since
    )
    if owner is not None:
        # a teacher sees activity in their own courses only; free-practice runs (no task) belong to none
        run_rows = run_rows.filter(visible_work(owner, TASK_TRACK))
        solved_rows = solved_rows.filter(visible_work(owner, TASK_TRACK))
    for created in run_rows.values_list(
        "created_at", flat=True
    ):
        if created.date() in runs:
            runs[created.date()] += 1
    solved_per_day = {day: 0 for day in days}
    for submitted in solved_rows.values_list("last_submitted_at", flat=True):
        if submitted.date() in solved_per_day:
            solved_per_day[submitted.date()] += 1

    next_task = _next_step(user, missions, tasks_by_mission, solved, completed_missions)
    profile = user.profile
    if owner is None:
        xp, level, streak, longest = profile.xp, profile.level, profile.current_streak, profile.longest_streak
    else:
        # level and streak are platform-wide: a teacher gets the XP earned in their own courses and no more
        xp = (
            Progress.objects.filter(user=user)
            .filter(visible_work(owner, MISSION_TRACK))
            .aggregate(xp=Sum("xp_earned"))["xp"]
            or 0
        )
        level = streak = longest = None

    return {
        "status": _status(has_activity, days_away, stuck, mean_attempts, len(solved_graded)),
        "summary": {
            "missions_done": len(completed_missions),
            "missions_total": len(missions),
            "steps_done": len(solved),
            "steps_total": len(tasks),
            "xp": xp,
            "level": level,
            "streak": streak,
            "longest_streak": longest,
            "days_away": days_away,
        },
        "attempts": {
            "mine": mean_attempts,
            "first_try_share": first_try,
            "solved": len(solved_graded),
            "cohort": cohort_mean,
            "cohort_size": cohort_size if cohort_mean is not None else None,
        },
        "stuck": stuck,
        "review": review,
        "rules": {"review_attempts": REVIEW_ATTEMPTS},
        "next": _step_ref(next_task, lang) if next_task else None,
        "activity": [
            {"date": day.isoformat(), "runs": runs[day], "solved": solved_per_day[day]}
            for day in days
        ],
        "missions": [
            {
                "id": mission.pk,
                "track_title": _pick(mission.location.track, lang) if mission.location.track_id else "",
                "title": _pick(mission, lang),
                "steps_done": sum(
                    1 for t in tasks_by_mission.get(mission.pk, []) if t.pk in solved
                ),
                "steps_total": len(tasks_by_mission.get(mission.pk, [])),
                "completed": mission.pk in completed_missions,
            }
            for mission in missions
        ],
    }
