"""Early Warning System: which learners need a teacher's attention right now.

A transparent, rule-based score. Every learner gets a level (``high`` /
``medium`` / ``ok``) plus the reasons behind it, so a teacher can see *why* a
name is on the list and decide what to do. The rules are deliberately simple:
the trained model of the analytics module will be added later as one more
signal, not as a replacement that cannot explain itself.

Signals (weights in ``WEIGHTS``):

* ``stuck_task`` - failed the same quiz/code step several times in a row
  (``HELP_AFTER_FAILURES`` or more; ``DEEP_STRUGGLE_FAILURES`` counts double).
* ``inactive`` - has unfinished work but has not shown up for a while.
* ``model_risk`` - the trained drop-out model (``game.risk``), if one is
  configured, puts the learner above its decision threshold.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from .metrics import _last_activity, _title, scoped_tasks
from .models import Progress, TaskProgress
from .risk import load_risk_model, risk_probabilities
from .services import HELP_AFTER_FAILURES

DEEP_STRUGGLE_FAILURES = 5
INACTIVE_SOON_DAYS = 3
INACTIVE_LONG_DAYS = 7

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
    """Non-staff learners doing the viewer's courses (all learners for a superuser)."""
    students = get_user_model().objects.filter(is_staff=False)
    if viewer.is_superuser:
        return students
    doing_my_courses = Progress.objects.filter(
        mission__location__track__owner=viewer
    ).values("user_id")
    return students.filter(id__in=doing_my_courses)


def assess_students(viewer, *, now=None):
    """{user_id: assessment} for every learner in the viewer's scope."""
    now = now or timezone.now()
    students = list(_scoped_learners(viewer).select_related("profile"))
    learner_ids = [student.pk for student in students]
    tasks = {task.pk: task for task in scoped_tasks(viewer)}

    open_missions = set(
        Progress.objects.filter(user_id__in=learner_ids, completed=False)
        .exclude(started_at__isnull=True)
        .values_list("user_id", flat=True)
    )
    worst = {}
    unsolved = TaskProgress.objects.filter(
        user_id__in=learner_ids,
        task_id__in=list(tasks),
        attempts__gte=HELP_AFTER_FAILURES,
    ).exclude(status="completed")
    for row in unsolved.values("user_id", "task_id", "attempts"):
        best = worst.get(row["user_id"])
        if best is None or row["attempts"] > best["attempts"]:
            worst[row["user_id"]] = row

    last_seen = _last_activity(learner_ids)
    model = load_risk_model()
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
            "xp": getattr(profile, "xp", 0),
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
            "high": sum(a["level"] == "high" for a in at_risk),
            "medium": sum(a["level"] == "medium" for a in at_risk),
        },
        "rules": {
            "stuck_failures": HELP_AFTER_FAILURES,
            "deep_failures": DEEP_STRUGGLE_FAILURES,
            "inactive_soon_days": INACTIVE_SOON_DAYS,
            "inactive_long_days": INACTIVE_LONG_DAYS,
            "model": bool(load_risk_model()),
        },
    }
