"""Tests for the daily streak engine (Profile.register_activity).

Each rule can break independently:
1. A completion starts/extends a per-day streak; same-day repeats don't
   double-count.
2. Consecutive days increment; a skipped day resets current_streak to 1.
3. longest_streak remembers the best run across resets.
4. Progress.complete() — the single real call path from the API — drives it.
5. streak_active / streak_at_risk reflect whether the run is alive / needs a
   nudge today.
6. Reaching 7 consecutive days lights up the previously-dormant streak_7
   achievement.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from game.achievements import evaluate_achievements
from game.models import Location, Mission, Progress

User = get_user_model()

DAY = datetime.timedelta(days=1)


def _user(username="hero"):
    # The post_save signal on User auto-creates the Profile.
    return User.objects.create_user(username=username, password="TestPass123!")


# ── register_activity unit logic ─────────────────────────────────────────────


@pytest.mark.django_db
def test_first_activity_starts_streak_at_one():
    p = _user().profile
    changed = p.register_activity(today=datetime.date(2026, 6, 5))
    assert changed is True
    assert p.current_streak == 1
    assert p.longest_streak == 1
    assert p.last_streak_date == datetime.date(2026, 6, 5)


@pytest.mark.django_db
def test_same_day_does_not_double_count():
    p = _user().profile
    day = datetime.date(2026, 6, 5)
    p.register_activity(today=day)
    changed = p.register_activity(today=day)
    assert changed is False
    assert p.current_streak == 1


@pytest.mark.django_db
def test_consecutive_days_increment():
    p = _user().profile
    p.register_activity(today=datetime.date(2026, 6, 5))
    p.register_activity(today=datetime.date(2026, 6, 6))
    p.register_activity(today=datetime.date(2026, 6, 7))
    assert p.current_streak == 3
    assert p.longest_streak == 3


@pytest.mark.django_db
def test_gap_resets_current_but_keeps_longest():
    p = _user().profile
    for d in (5, 6, 7):
        p.register_activity(today=datetime.date(2026, 6, d))
    # skip the 8th, resume on the 9th → run restarts at 1, record stays 3
    p.register_activity(today=datetime.date(2026, 6, 9))
    assert p.current_streak == 1
    assert p.longest_streak == 3


# ── Progress.complete drives the streak ──────────────────────────────────────


@pytest.mark.django_db
def test_complete_mission_updates_streak():
    user = _user()
    loc = Location.objects.create(title="Intro", description="loc")
    mission = Mission.objects.create(location=loc, title="Hello", xp_reward=10)
    Progress.objects.create(user=user, mission=mission).complete()
    user.profile.refresh_from_db()
    assert user.profile.current_streak == 1
    assert user.profile.last_streak_date == timezone.localdate()


# ── display / reminder flags ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_streak_active_and_at_risk_flags():
    today = timezone.localdate()
    p = _user("a").profile
    # completed yesterday: alive but not yet extended today → at risk
    p.register_activity(today=today - DAY)
    assert p.streak_active is True
    assert p.streak_at_risk is True
    # completed today: alive and already counted → not at risk
    p.register_activity(today=today)
    assert p.streak_active is True
    assert p.streak_at_risk is False


@pytest.mark.django_db
def test_streak_dead_after_multi_day_gap():
    today = timezone.localdate()
    p = _user("b").profile
    p.register_activity(today=today - datetime.timedelta(days=3))
    assert p.streak_active is False
    assert p.streak_at_risk is False


# ── achievement wake-up ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_streak_7_achievement_lights_up():
    user = _user()
    start = datetime.date(2026, 6, 1)
    for i in range(7):
        user.profile.register_activity(today=start + i * DAY)
    assert user.profile.longest_streak == 7
    assert "streak_7" in evaluate_achievements(user)


# ── serializer exposes streak to the frontend ────────────────────────────────


@pytest.mark.django_db
def test_profile_serializer_exposes_streak_fields():
    from users.serializers import ProfileSerializer

    p = _user().profile
    p.register_activity(today=timezone.localdate() - DAY)  # yesterday → at risk
    data = ProfileSerializer(p).data
    assert data["current_streak"] == 1
    assert data["longest_streak"] == 1
    assert data["streak_active"] is True
    assert data["streak_at_risk"] is True


@pytest.mark.django_db
def test_profile_me_endpoint_includes_streak():
    # The live endpoint the frontend actually calls (/profile/me/) is served by
    # ProfileMeView's hand-built payload, NOT ProfileSerializer — so it needs its
    # own coverage, or the streak silently never reaches the UI.
    from rest_framework.test import APIClient

    user = _user()
    user.profile.register_activity(today=timezone.localdate() - DAY)
    client = APIClient()
    client.force_authenticate(user=user)

    data = client.get("/api/profile/me/").json()
    assert data["current_streak"] == 1
    assert data["longest_streak"] == 1
    assert data["streak_active"] is True
    assert data["streak_at_risk"] is True
