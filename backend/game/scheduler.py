"""In-process daily scheduler: runs ``send_streak_reminders`` and ``snapshot_early_warning`` once a day.

A daemon thread (started only when ``ENABLE_STREAK_SCHEDULER=1``) wakes at the
configured UTC hour and runs the commands. Both are idempotent per day (reminders
are stamped, the snapshot is one row per learner per date), so a missed or
duplicated run is harmless.
"""

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_started = False
_start_lock = threading.Lock()


def _seconds_until(hour, minute, *, now=None):
    """Seconds from *now* (UTC) until the next occurrence of hour:minute UTC."""
    now = now or datetime.now(timezone.utc)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _run_once():
    from django.core.management import call_command

    # each job on its own: one failing must not stop the other, nor the loop
    for command in ("send_streak_reminders", "snapshot_early_warning"):
        try:
            call_command(command)
        except Exception:  # noqa: BLE001
            logger.exception("%s failed", command)


def _loop(hour, minute):
    while True:
        time.sleep(_seconds_until(hour, minute))
        _run_once()
        time.sleep(60)  # step past the target minute so we don't double-fire


def start():
    """Start the daily scheduler thread once per process (idempotent)."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True

    hour = int(os.environ.get("STREAK_REMINDER_HOUR", "18"))
    minute = int(os.environ.get("STREAK_REMINDER_MINUTE", "0"))
    thread = threading.Thread(
        target=_loop,
        args=(hour, minute),
        name="streak-reminder-scheduler",
        daemon=True,
    )
    thread.start()
    logger.info("Streak reminder scheduler started (%02d:%02d UTC)", hour, minute)
