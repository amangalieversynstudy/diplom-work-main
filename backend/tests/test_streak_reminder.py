"""Tests for the send_streak_reminders management command.

Guarantees:
1. Only genuinely at-risk players with a usable email get reminded — players
   who already practised today, whose streak is already broken, who have no
   email, who are inactive, or who have no streak are skipped.
2. The send is idempotent within a day (no double email if the job re-runs).
3. ``--dry-run`` lists recipients without sending or stamping anyone.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

User = get_user_model()

DAY = datetime.timedelta(days=1)


def _player(username, *, email="", streak=0, last_date=None, active=True):
    user = User.objects.create_user(
        username=username, password="TestPass123!", email=email, is_active=active
    )
    p = user.profile
    p.current_streak = streak
    p.last_streak_date = last_date
    p.save(update_fields=["current_streak", "last_streak_date"])
    return user


@pytest.mark.django_db
def test_reminds_only_at_risk_players_with_email(mailoutbox):
    today = timezone.localdate()
    yesterday = today - DAY

    at_risk = _player("atrisk", email="a@example.com", streak=4, last_date=yesterday)
    _player("donetoday", email="b@example.com", streak=4, last_date=today)
    _player("dead", email="c@example.com", streak=4, last_date=today - 3 * DAY)
    _player("noemail", email="", streak=4, last_date=yesterday)
    _player("inactive", email="d@example.com", streak=4, last_date=yesterday, active=False)
    _player("nostreak", email="e@example.com", streak=0, last_date=yesterday)

    call_command("send_streak_reminders")

    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["a@example.com"]
    assert "4" in msg.body  # streak length mentioned
    at_risk.profile.refresh_from_db()
    assert at_risk.profile.last_streak_reminder == today


@pytest.mark.django_db
def test_idempotent_within_same_day(mailoutbox):
    yesterday = timezone.localdate() - DAY
    _player("atrisk", email="a@example.com", streak=2, last_date=yesterday)

    call_command("send_streak_reminders")
    call_command("send_streak_reminders")  # re-run the same day

    assert len(mailoutbox) == 1  # not emailed twice


@pytest.mark.django_db
def test_dry_run_sends_nothing(mailoutbox):
    yesterday = timezone.localdate() - DAY
    user = _player("atrisk", email="a@example.com", streak=2, last_date=yesterday)

    call_command("send_streak_reminders", "--dry-run")

    assert len(mailoutbox) == 0
    user.profile.refresh_from_db()
    assert user.profile.last_streak_reminder is None  # not stamped


def test_scheduler_seconds_until_next_utc_slot():
    # Pure helper that drives the in-process daily scheduler (game/scheduler.py).
    from datetime import datetime, timezone as tz

    from game.scheduler import _seconds_until

    before = datetime(2026, 6, 5, 10, 0, 0, tzinfo=tz.utc)  # 8h before 18:00
    assert _seconds_until(18, 0, now=before) == 8 * 3600

    after = datetime(2026, 6, 5, 20, 0, 0, tzinfo=tz.utc)  # slot passed → tomorrow
    assert _seconds_until(18, 0, now=after) == 22 * 3600
