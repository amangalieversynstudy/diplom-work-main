"""Early Warning System: which learners need a teacher's attention right now.

A transparent, rule-based score. Every learner gets a level (``high`` /
``medium`` / ``ok``) plus the reasons behind it, so a teacher can see *why* a
name is on the list and decide what to do. The rules are deliberately simple:
the trained model of the analytics module will be added later as one more
signal, not as a replacement that cannot explain itself.

Signals (weights in ``WEIGHTS``):

* ``stuck_task`` - failed the same quiz/code step several times in a row
  (``HELP_AFTER_FAILURES`` or more; ``DEEP_STRUGGLE_FAILURES`` counts double),
  and tried it within the last ``STUCK_RECENT_DAYS``.
* ``inactive`` - has unfinished work but has not shown up for a while.
* ``model_risk`` - the trained drop-out model (``game.risk``), if one is
  configured, puts the learner above its decision threshold.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from .classes import MISSION_TRACK, TASK_TRACK, owner_scope, visible_learners, visible_work
from .metrics import ABANDON_WINDOW_DAYS, _last_activity, _title, scoped_tasks
from .models import Progress, TaskProgress
from .risk import load_risk_model, risk_probabilities
from .services import HELP_AFTER_FAILURES

DEEP_STRUGGLE_FAILURES = 5
INACTIVE_SOON_DAYS = 3
INACTIVE_LONG_DAYS = 7
# A step failed this long ago and not touched since is no longer "stuck now": the learner moved on
# (or went quiet, which the inactivity signal catches). Same length as the "left" window.
STUCK_RECENT_DAYS = ABANDON_WINDOW_DAYS

WEIGHTS = {
    "stuck_task": 2,
    "deep_struggle": 4,
    "inactive_long": 3,
    "inactive_soon": 1,
    "model_risk": 2,
}
HIGH_SCORE = 4
MEDIUM_SCORE = 2

LEVEL_ORDER = {"high": 0, "medium": 1, "ok": 2}


def _level(score):
    if score >= HIGH_SCORE:
        return "high"
    if score >= MEDIUM_SCORE:
        return "medium"
    return "ok"


def _scoped_learners(viewer):
    """Learners the viewer may see: those who joined their classes or took their public courses
    (all learners for a superuser). See ``classes.visible_learners``."""
    return visible_learners(viewer)


scoped_learners = _scoped_learners  # public name for the teacher's per-student screen


def assess_students(viewer, *, now=None, consented_only=False):
    """{user_id: assessment} for every learner in the viewer's scope.

    ``consented_only`` keeps just the learners who agreed to the research (the pilot report and the
    daily snapshots use it; the teacher's own list does not need consent).
    """
    now = now or timezone.now()
    scope = _scoped_learners(viewer)
    if consented_only:
        scope = scope.filter(profile__research_consent=True)
    students = list(scope.select_related("profile"))
    learner_ids = [student.pk for student in students]
    # three wrong guesses at an "explain" question say little about being stuck: leave them out
    tasks = {task.pk: task for task in scoped_tasks(viewer) if task.kind != "explain"}

    # Only work the viewer may see counts: their own courses, a closed one only while the learner is enrolled
    # (Q() for a superuser, so the pilot report and H3 snapshots are unchanged).
    open_missions = set(
        Progress.objects.filter(user_id__in=learner_ids, completed=False)
        .filter(visible_work(viewer, MISSION_TRACK))
        .exclude(started_at__isnull=True)
        .values_list("user_id", flat=True)
    )
    worst = {}
    unsolved = TaskProgress.objects.filter(
        user_id__in=learner_ids,
        task_id__in=list(tasks),
        attempts__gte=HELP_AFTER_FAILURES,
        last_submitted_at__gte=now - timedelta(days=STUCK_RECENT_DAYS),
    ).filter(visible_work(viewer, TASK_TRACK)).exclude(status="completed")
    for row in unsolved.values("user_id", "task_id", "attempts"):
        best = worst.get(row["user_id"])
        if best is None or row["attempts"] > best["attempts"]:
            worst[row["user_id"]] = row

    owner = owner_scope(viewer)
    last_seen = _last_activity(learner_ids, owner=owner)
    # The model reads platform-wide behaviour (its features cannot be scoped to one course), so only a superuser
    # gets its probability; a teacher's list stays within what the learner agreed to show them.
    model = load_risk_model() if owner is None else None
    course_xp = {}
    if owner is not None:
        course_xp = dict(
            Progress.objects.filter(user_id__in=learner_ids)
            .filter(visible_work(viewer, MISSION_TRACK))
            .values("user_id")
            .annotate(xp=Sum("xp_earned"))
            .order_by()
            .values_list("user_id", "xp")
        )
    chances = risk_probabilities(model, learner_ids, now) if model else {}
    assessments = {}
    for student in students:
        reasons = []
        score = 0
        stuck = worst.get(student.pk)
        if stuck:
            deep = stuck["attempts"] >= DEEP_STRUGGLE_FAILURES
            score += WEIGHTS["deep_struggle" if deep else "stuck_task"]
            task = tasks[stuck["task_id"]]
            reasons.append(
                {
                    "code": "stuck_task",
                    "failures": stuck["attempts"],
                    "task_id": task.pk,
                    "task_title": _title(task) if (task.title or task.title_ru) else "",
                    "task_type": task.task_type,
                    "mission_title": _title(task.mission),
                }
            )

        seen = last_seen.get(student.pk)
        days = (now - seen).days if seen else None
        has_open_work = student.pk in open_missions or stuck is not None
        if has_open_work and (days is None or days >= INACTIVE_SOON_DAYS):
            long_gone = days is None or days >= INACTIVE_LONG_DAYS
            score += WEIGHTS["inactive_long" if long_gone else "inactive_soon"]
            reasons.append({"code": "inactive", "days": days})

        chance = chances.get(student.pk)
        if chance is not None and has_open_work and chance >= model.threshold:
            score += WEIGHTS["model_risk"]
            reasons.append({"code": "model_risk", "probability": round(chance, 2)})

        profile = getattr(student, "profile", None)
        assessments[student.pk] = {
            "id": student.pk,
            "username": student.username,
            "display_name": student.display_name or "",
            "level": _level(score),
            "score": score,
            "reasons": reasons,
            "failures": stuck["attempts"] if stuck else 0,
            "risk_probability": round(chance, 3) if chance is not None else None,
            "last_active": seen.isoformat() if seen else None,
            "days_inactive": days,
            # a teacher sees XP earned in their own courses, a superuser the profile total
            "xp": getattr(profile, "xp", 0) if owner is None else (course_xp.get(student.pk) or 0),
        }
    return assessments


def early_warning(viewer, *, now=None):
    """Learners that need attention, most urgent first, with a small summary."""
    everyone = assess_students(viewer, now=now)
    at_risk = sorted(
        (a for a in everyone.values() if a["level"] != "ok"),
        key=lambda a: (LEVEL_ORDER[a["level"]], -a["score"], a["username"]),
    )
    return {
        "students": at_risk,
        "summary": {
            "total": len(everyone),
            # learners who did anything at all: an empty list is only good news when there is data behind it
            "with_activity": sum(a["last_active"] is not None for a in everyone.values()),
            "high": sum(a["level"] == "high" for a in at_risk),
            "medium": sum(a["level"] == "medium" for a in at_risk),
        },
        "rules": {
            "stuck_failures": HELP_AFTER_FAILURES,
            "deep_failures": DEEP_STRUGGLE_FAILURES,
            "inactive_soon_days": INACTIVE_SOON_DAYS,
            "inactive_long_days": INACTIVE_LONG_DAYS,
            "model": bool(load_risk_model()) and owner_scope(viewer) is None,
        },
    }
