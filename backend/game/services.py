"""Server-side rules for progressing through missions and grading tasks.

Everything that decides whether a learner may open a step, whether an answer is
right, and whether a mission is finished lives here, so the API views and the
WebSocket runner share one implementation and the browser is never trusted to
say "I solved it".
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status as http
from rest_framework.exceptions import APIException

from .models import MissionTask, Progress, TaskProgress

# Keys of ``MissionTask.data`` that are safe to show to learners. Anything else
# (correct_answer, expected_output, sampleOutput, isCorrect ...) stays on the
# server. New keys must be added here on purpose.
PUBLIC_DATA_KEYS = ("language", "starter")
PUBLIC_OPTION_KEYS = ("value", "label")


class RuleViolation(APIException):
    """A learner-facing rule was broken; carries its own HTTP status."""

    def __init__(self, detail, status_code=http.HTTP_400_BAD_REQUEST):
        super().__init__(detail=detail)
        self.status_code = status_code


# ── visibility ──────────────────────────────────────────────────────────────


def only_published(queryset, user, track_lookup):
    """Hide content of unpublished (draft) tracks from everyone but superusers.

    ``track_lookup`` is the path from the model to its Track, e.g.
    ``"location__track"`` for missions. Content without a track stays visible.
    """
    if user is not None and getattr(user, "is_superuser", False):
        return queryset
    return queryset.filter(
        Q(**{f"{track_lookup}__isnull": True}) | Q(**{f"{track_lookup}__is_active": True})
    )


def public_task_data(task):
    """The part of ``task.data`` a learner is allowed to see (no answer key)."""
    data = task.data if isinstance(task.data, dict) else {}
    public = {key: data[key] for key in PUBLIC_DATA_KEYS if key in data}
    options = data.get("options")
    if isinstance(options, list):
        public["options"] = [
            {key: opt[key] for key in PUBLIC_OPTION_KEYS if key in opt}
            if isinstance(opt, dict)
            else opt
            for opt in options
        ]
    return public


# ── access rules ────────────────────────────────────────────────────────────


def check_mission_access(user, mission):
    """Raise RuleViolation unless *user* may work on *mission* right now."""
    if not mission.is_active:
        raise RuleViolation("Mission is inactive", http.HTTP_400_BAD_REQUEST)
    if user.profile.level < mission.min_level:
        raise RuleViolation("Level too low", http.HTTP_403_FORBIDDEN)
    prerequisite_ids = set(mission.prerequisites.values_list("id", flat=True))
    if prerequisite_ids:
        done = set(
            Progress.objects.filter(
                user=user, completed=True, mission_id__in=prerequisite_ids
            ).values_list("mission_id", flat=True)
        )
        if prerequisite_ids - done:
            raise RuleViolation("Prerequisites not completed", http.HTTP_403_FORBIDDEN)


def _completed_task_ids(user, task_ids):
    return set(
        TaskProgress.objects.filter(
            user=user, task_id__in=task_ids, status="completed"
        ).values_list("task_id", flat=True)
    )


def check_task_order(user, task):
    """Required steps must be finished in order (the UI locks them the same way)."""
    earlier = set(
        MissionTask.objects.filter(mission_id=task.mission_id, is_required=True)
        .filter(Q(order__lt=task.order) | Q(order=task.order, id__lt=task.id))
        .values_list("id", flat=True)
    )
    if earlier - _completed_task_ids(user, earlier):
        raise RuleViolation("Finish the previous steps first", http.HTTP_409_CONFLICT)


def require_mission_tasks_done(user, mission):
    """A mission can only be completed once every required task is solved."""
    required = set(
        mission.tasks.filter(is_required=True).values_list("id", flat=True)
    )
    if not required:
        raise RuleViolation(
            "This mission has no tasks to complete yet", http.HTTP_409_CONFLICT
        )
    if required - _completed_task_ids(user, required):
        raise RuleViolation("Finish all required tasks first", http.HTTP_409_CONFLICT)


def mission_stars(user, mission):
    """0-3 stars from how many extra tries the required tasks needed."""
    attempts = TaskProgress.objects.filter(
        user=user, task__mission=mission, task__is_required=True
    ).values_list("attempts", flat=True)
    extra = sum(max(0, count - 1) for count in attempts)
    if extra == 0:
        return 3
    return 2 if extra <= 3 else 1


# ── grading ─────────────────────────────────────────────────────────────────


def _norm(value):
    return str(value).strip().lower()


def _norm_output(text):
    return str(text).replace("\r\n", "\n").strip()


def quiz_answer_key(task):
    """Normalised right answer of a quiz, or None if the task has no key."""
    data = task.data if isinstance(task.data, dict) else {}
    key = data.get("correct_answer")
    if key not in (None, ""):
        return _norm(key)
    for option in data.get("options") or []:
        if isinstance(option, dict) and option.get("isCorrect"):
            return _norm(option.get("value", option.get("label", "")))
    return None


def grade_quiz(task, answer):
    key = quiz_answer_key(task)
    if key is None:
        raise RuleViolation("This quiz has no answer key", http.HTTP_400_BAD_REQUEST)
    return _norm(answer) == key


def code_run_passed(task, exit_code, stdout):
    """A code task passes when the run succeeded and, if the task defines an
    expected output, the program printed exactly that."""
    if exit_code != 0:
        return False
    data = task.data if isinstance(task.data, dict) else {}
    expected = _norm_output(data.get("expected_output") or "")
    return not expected or _norm_output(stdout) == expected


def prepare_code_task(user, task_id):
    """Load a code task for a run and check that *user* may attempt it."""
    if isinstance(task_id, bool) or not isinstance(task_id, int):
        raise RuleViolation("task_id must be an integer", http.HTTP_400_BAD_REQUEST)
    task = (
        only_published(
            MissionTask.objects.select_related("mission"),
            user,
            "mission__location__track",
        )
        .filter(pk=task_id, task_type="code")
        .first()
    )
    if task is None:
        raise RuleViolation("Task not found", http.HTTP_404_NOT_FOUND)
    check_mission_access(user, task.mission)
    check_task_order(user, task)
    return task


@transaction.atomic
def record_task_attempt(user, task, *, passed, score, answer):
    """Store one graded attempt and return the learner's TaskProgress.

    ``attempts`` counts tries up to and including the first success, so the
    "attempts to success" metric is not polluted by later re-runs of a task
    that is already solved. The returned object carries ``counted``: whether
    this call was one of those counted tries.
    """
    progress, _ = Progress.objects.get_or_create(user=user, mission=task.mission)
    if progress.started_at is None:
        progress.start()

    task_progress, _ = TaskProgress.objects.get_or_create(user=user, task=task)
    task_progress = TaskProgress.objects.select_for_update().get(pk=task_progress.pk)
    task_progress.counted = task_progress.status != "completed"
    if task_progress.counted:
        task_progress.attempts += 1
        task_progress.last_submitted_at = timezone.now()
        task_progress.best_score = max(task_progress.best_score or 0, score)
        task_progress.answer = answer
        task_progress.status = "completed" if passed else "in_progress"
        task_progress.save()
    return task_progress


def progress_payload(task_progress):
    """Small JSON-safe view of a TaskProgress for API and WebSocket replies."""
    return {
        "id": task_progress.id,
        "task": task_progress.task_id,
        "status": task_progress.status,
        "attempts": task_progress.attempts,
        "best_score": task_progress.best_score,
        "answer": task_progress.answer,
    }


def grade_code_run(user, task, code, stdout, exit_code):
    """Grade a finished run of a code task and record the attempt."""
    passed = code_run_passed(task, exit_code, stdout)
    task_progress = record_task_attempt(
        user,
        task,
        passed=passed,
        score=100 if passed else 0,
        answer={"code": code},
    )
    return {
        "passed": passed,
        "progress": progress_payload(task_progress),
        "counted": task_progress.counted,
    }
