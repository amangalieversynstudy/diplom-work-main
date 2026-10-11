"""Server-side rules for progressing through missions and grading tasks.

Everything that decides whether a learner may open a step, whether an answer is
right, and whether a mission is finished lives here, so the API views and the
WebSocket runner share one implementation and the browser is never trusted to
say "I solved it".
"""

import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status as http
from rest_framework.exceptions import APIException

from . import help as help_module
from .achievements import evaluate_achievements
from .models import MissionTask, Progress, TaskProgress
from .variants import personalize
from .runner import execute_python_code

# Keys of ``MissionTask.data`` that are safe to show to learners. Anything else
# (correct_answer, expected_output, sampleOutput, isCorrect ...) stays on the
# server. New keys must be added here on purpose.
PUBLIC_DATA_KEYS = ("language", "starter")
PUBLIC_OPTION_KEYS = ("value", "label")

# After this many failed attempts in a row on one step the platform offers help
# (hint scroll, AI mentor) instead of letting the learner grind alone. The same
# number marks the learner as "struggling" for the teacher's early warning.
HELP_AFTER_FAILURES = 3


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
    # the texts stay private until an item is spent; only their existence is public
    if help_module.has_hint(task):
        public["has_hint"] = True
    if help_module.has_skeleton(task):
        public["has_skeleton"] = True
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


HIDDEN_CHECK_TIMEOUT = 5


def hidden_check_of(task):
    """The teacher's hidden check (Python source) of a code task, or ""."""
    data = task.data if isinstance(task.data, dict) else {}
    check = data.get("hidden_check")
    return check.strip() if isinstance(check, str) else ""


def run_hidden_check(task, code):
    """Run the learner's code followed by the task's hidden check.

    Matching the printed output is not enough: ``print("Charged")`` matches
    without any function behind it. The check calls the learner's own functions
    with other values. It runs in a separate, silent run, and passes only if the
    program reaches its end and prints a one-time token that the learner never
    sees (an early ``exit()`` or a faked output cannot produce it).

    Returns True/False, or None when the sandbox itself failed (that must not
    count as a failed attempt).
    """
    check = hidden_check_of(task)
    if not check:
        return True
    token = secrets.token_hex(16)
    result = execute_python_code(
        f"{code}\n\n{check}\nprint({token!r})\n", timeout=HIDDEN_CHECK_TIMEOUT
    )
    if result.get("infra"):
        return None
    return result.get("status") == "success" and token in (result.get("output") or "")


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
    # what the first solve paid out; the client shows it and reacts to a level-up
    task_progress.xp_added = 0
    task_progress.leveled_up = False
    task_progress.new_level = None
    if task_progress.counted:
        task_progress.attempts += 1
        task_progress.last_submitted_at = timezone.now()
        task_progress.best_score = max(task_progress.best_score or 0, score)
        task_progress.answer = answer
        task_progress.status = "completed" if passed else "in_progress"
        task_progress.save()
        if passed:
            _pay_for_solved_step(user, task, progress, task_progress)
    return task_progress


def _pay_for_solved_step(user, task, progress, task_progress):
    """The first solve of a step pays its XP and counts as a day of learning.

    Only the first solve: re-running a solved step changes nothing. The XP is the
    step's own ``xp_reward`` (the mission's reward is a completion bonus on top),
    so the reward the course author typed in Studio is the reward learners get.
    """
    from users.models import Profile

    from .signals import refresh_leaderboard

    profile = Profile.objects.select_for_update().get(user=user)
    profile.register_activity()  # a solved step is a day of learning, not only a finished mission
    reward = max(0, int(task.xp_reward or 0))
    if reward:
        leveled_up, _old, new_level = profile.add_xp(reward)
        Progress.objects.filter(pk=progress.pk).update(xp_earned=F("xp_earned") + reward)
        task_progress.xp_added = reward
        task_progress.leveled_up = leveled_up
        task_progress.new_level = new_level
        refresh_leaderboard(user, getattr(task.mission.location, "track", None), profile=profile)
    # Level and streak now move with every solved step, so a badge such as "level 5" or "7 days"
    # opens here and not only at the end of the next mission (the profile showed a full bar with
    # the badge still locked).
    user.profile = profile
    task_progress.new_achievements = evaluate_achievements(user)


def failures_in_a_row(task_progress):
    """Failed attempts since the learner last solved (or started) the step.

    ``attempts`` counts tries up to the first success, so for an unsolved step it
    is exactly the number of failures in a row.
    """
    if task_progress.status == "completed":
        return 0
    return task_progress.attempts


ARM_OFFER = "offer"
ARM_CONTROL = "control"


def help_arm(user_id):
    """Which experiment arm a learner is in: sees the help prompt or not.

    Stable for a given learner (a hash of the id, no table needed) and driven by
    ``HELP_OFFER_SHARE``: 100 (the default) puts everyone in ``offer``.
    """
    share = max(0, min(100, int(getattr(settings, "HELP_OFFER_SHARE", 100))))
    if share >= 100:
        return ARM_OFFER
    digest = hashlib.sha256(f"help-offer:{user_id}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return ARM_OFFER if bucket < share else ARM_CONTROL


def help_offer(task_progress):
    """The help offer for this step, or None (not stuck, or in the control arm)."""
    failures = failures_in_a_row(task_progress)
    if failures < HELP_AFTER_FAILURES:
        return None
    if task_progress.task.kind == "explain":
        return None  # there is no hint to offer for a question about one's own solution
    if help_arm(task_progress.user_id) != ARM_OFFER:
        return None
    return {"failures": failures, "threshold": HELP_AFTER_FAILURES}


def progress_payload(task_progress):
    """Small JSON-safe view of a TaskProgress for API and WebSocket replies."""
    return {
        "id": task_progress.id,
        "task": task_progress.task_id,
        "status": task_progress.status,
        "attempts": task_progress.attempts,
        "best_score": task_progress.best_score,
        "answer": task_progress.answer,
        "help_offer": help_offer(task_progress),
        "xp_added": getattr(task_progress, "xp_added", 0),
        "leveled_up": getattr(task_progress, "leveled_up", False),
        "new_level": getattr(task_progress, "new_level", None),
        # slugs of badges opened by this step (the client shows a toast for each)
        "new_achievements": getattr(task_progress, "new_achievements", []),
    }


NOT_CHECKED = object()  # the hidden check has not been run by the caller


def precheck_hidden(user, task, code, stdout, exit_code):
    """Run the slow hidden check ahead of grade_code_run, without touching the DB.

    Meant for a worker thread: the sandbox call takes seconds and must not hold
    the shared database thread. Returns True/False/None like run_hidden_check,
    or NOT_CHECKED when the run does not reach the hidden check at all.
    """
    task = personalize(task, user.pk)
    if not code_run_passed(task, exit_code, stdout):
        return NOT_CHECKED
    return run_hidden_check(task, code)


def grade_code_run(user, task, code, stdout, exit_code, hidden_passed=NOT_CHECKED):
    """Grade a finished run of a code task and record the attempt.

    ``hidden_passed`` is the result of a hidden check the caller already ran
    (see precheck_hidden); when absent the check is run here.

    Returns None when the hidden check could not be run (broken sandbox): the
    attempt is then neither recorded nor counted.
    """
    task = personalize(task, user.pk)  # the learner is graded on their own variant of the step
    passed = code_run_passed(task, exit_code, stdout)
    hidden_failed = False
    if passed:
        checked = run_hidden_check(task, code) if hidden_passed is NOT_CHECKED else hidden_passed
        if checked is None:
            return None
        hidden_failed = not checked
        passed = checked
    task_progress = record_task_attempt(
        user,
        task,
        passed=passed,
        score=100 if passed else 0,
        answer={"code": code},
    )
    return {
        "passed": passed,
        # the printed output was right but the hidden check failed
        "hidden_failed": hidden_failed,
        "progress": progress_payload(task_progress),
        "counted": task_progress.counted,
    }
