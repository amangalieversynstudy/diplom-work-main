"""Behavioural footprint: what learners do, recorded for teachers and research.

Recording must never get in the way of learning. Every write here is wrapped:
a failure is logged and swallowed, and it runs in its own savepoint so a failed
insert cannot poison the caller's transaction.
"""

import logging
import re

from django.db import transaction

from .models import CodeRun, LearningEvent, MissionTask
from .runner import INFRASTRUCTURE_REASONS, REASON_OUTPUT_LIMIT, REASON_TIMEOUT
from .services import HELP_AFTER_FAILURES, grade_code_run, only_published

logger = logging.getLogger(__name__)

# "NameError: name 'x' is not defined", "requests.exceptions.HTTPError: ...",
# "SystemExit: 3" - the exception class is the part before the colon.
_EXCEPTION_LINE = re.compile(
    r"^(?:[A-Za-z_]\w*\.)*((?:[A-Za-z_]\w*)?(?:Error|Exception|Exit|Interrupt))\b"
)


def exception_name(stderr):
    """Class name of the exception a Python traceback ended with, or ''."""
    for line in reversed(str(stderr).splitlines()):
        match = _EXCEPTION_LINE.match(line.strip())
        if match:
            return match.group(1)
    return ""


def _last_line(text, limit=200):
    for line in reversed(str(text).splitlines()):
        if line.strip():
            return line.strip()[:limit]
    return ""


def classify_run(exit_code, stderr, reasons, passed):
    """(outcome, error_type, error_message) of a finished run.

    ``reasons`` are the machine-readable reasons of the runner's error events;
    ``passed`` is the grading verdict, or None for an ungraded (free) run.
    """
    reasons = set(reasons)
    if reasons & INFRASTRUCTURE_REASONS:
        return "runner_error", "", ""
    if REASON_TIMEOUT in reasons:
        return "timeout", "Timeout", ""
    if REASON_OUTPUT_LIMIT in reasons:
        return "output_limit", "OutputLimit", ""
    if exit_code == 0:
        return ("wrong_output" if passed is False else "success"), "", ""
    return "error", exception_name(stderr) or "NonZeroExit", _last_line(stderr)


def find_task(task_id, user=None):
    """The task with this id (visible to *user* if given), or None.

    Used for optional ``task_id`` fields sent by the client: anything that is
    not a real, visible task simply means "no task".
    """
    if isinstance(task_id, bool) or not isinstance(task_id, int):
        return None
    tasks = MissionTask.objects.select_related("mission")
    if user is not None:
        tasks = only_published(tasks, user, "mission__location__track")
    return tasks.filter(pk=task_id).first()


def log_event(user, event_type, *, task=None, mission=None, **meta):
    """Append one event to the learner's timeline. Never raises."""
    try:
        with transaction.atomic():
            LearningEvent.objects.create(
                user=user,
                event_type=event_type,
                task=task,
                mission=mission if mission is not None else getattr(task, "mission", None),
                meta=meta,
            )
    except Exception:
        logger.exception("Could not record learning event %s", event_type)


def log_help_offer(user, task, progress):
    """Record that the learner was offered help; once, at the threshold.

    ``progress`` is the ``progress_payload`` of the attempt that was just
    counted. Later failures keep the offer visible but do not repeat the event.
    """
    offer = progress.get("help_offer")
    if offer and offer["failures"] == HELP_AFTER_FAILURES:
        log_event(user, LearningEvent.HELP_OFFERED, task=task, failures=offer["failures"])


def record_code_run(
    user,
    task,
    *,
    code,
    stdout,
    stderr,
    exit_code,
    duration,
    reasons,
    passed=None,
    attempt_no=None,
    after_solved=False,
):
    """Store the measurements of one run. Never raises."""
    outcome, error_type, error_message = classify_run(
        exit_code, stderr, reasons, passed
    )
    try:
        with transaction.atomic():
            CodeRun.objects.create(
                user=user,
                task=task,
                outcome=outcome,
                error_type=error_type,
                error_message=error_message,
                exit_code=exit_code,
                duration_ms=max(0, int(float(duration or 0) * 1000)),
                code_length=len(code or ""),
                stdout_size=len(stdout or ""),
                stderr_size=len(stderr or ""),
                passed=passed,
                attempt_no=attempt_no,
                after_solved=after_solved,
            )
    except Exception:
        logger.exception("Could not record code run")


def finish_code_run(
    user, task, *, code, stdout, stderr, exit_code, duration, reasons
):
    """Handle a run that reached its end: grade it (if it belongs to a task),
    record it, and return the task verdict (None for free practice).

    Runs cut short by the infrastructure (sandbox failure, unavailable, stopped
    by the learner) are recorded but never graded: a broken sandbox must not
    count as a failed attempt.
    """
    verdict = None
    counted = False
    if task is not None and not (set(reasons) & INFRASTRUCTURE_REASONS):
        verdict = grade_code_run(user, task, code, stdout, exit_code)
        counted = verdict.pop("counted")
        if counted and not verdict["passed"]:
            log_help_offer(user, task, verdict["progress"])

    record_code_run(
        user,
        task,
        code=code,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        duration=duration,
        reasons=reasons,
        passed=verdict["passed"] if verdict else None,
        attempt_no=verdict["progress"]["attempts"] if verdict else None,
        after_solved=bool(verdict) and not counted,
    )
    return verdict
