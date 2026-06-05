"""Lightweight in-process daily scheduler for streak reminders.

Runs *inside* the existing web service, so no extra Railway service (or
dependency) is needed. Spawns one daemon thread that wakes once a day at the
configured UTC time and runs the ``send_streak_reminders`` management command.

Enabled only when ``ENABLE_STREAK_SCHEDULER=1`` so it never starts during
tests, migrations or one-off management commands. Daily idempotency lives in
the command itself (``Profile.last_streak_reminder``), so even if several web
workers each run this thread, no player is emailed twice.

Caveat: a missed slot (service restarting/asleep at the target minute) is not
retried until the next day — fine for a daily nudge, and you can always run
``python manage.py send_streak_reminders`` manually.
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

    try:
        call_command("send_streak_reminders")
    except Exception:  # noqa: BLE001 — a failure must never kill the loop
        logger.exception("send_streak_reminders failed")


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
