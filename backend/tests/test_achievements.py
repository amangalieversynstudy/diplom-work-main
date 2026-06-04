"""Tests for the achievements catalog, evaluation, and API surface.

The catalog lives in code (``game/achievements.py``); only unlock facts are
persisted (``game.models.UserAchievement``). These tests cover the three things
that can break independently: the condition logic, the idempotent persistence,
and the two HTTP entry points (the standalone endpoint and the mission-complete
side effect that surfaces fresh unlocks for a toast).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.achievements import achievements_for, evaluate_achievements
from game.models import (
    Location,
    Mission,
    Progress,
    Track,
    UserAchievement,
)

User = get_user_model()


def _user(username="hero"):
    return User.objects.create_user(username=username, password="TestPass123!")


@pytest.mark.django_db
def test_first_mission_unlocks_and_is_idempotent():
    """Completing one mission earns ``first_mission`` exactly once."""
    user = _user()
    loc = Location.objects.create(title="Intro", description="First location")
    mission = Mission.objects.create(location=loc, title="Hello", xp_reward=10)
    Progress.objects.create(user=user, mission=mission, completed=True)

    newly = evaluate_achievements(user)
    assert "first_mission" in newly
    assert UserAchievement.objects.filter(
        user=user, slug="first_mission"
    ).count() == 1

    # Second pass earns nothing new and creates no duplicate row.
    assert evaluate_achievements(user) == []
    assert UserAchievement.objects.filter(
        user=user, slug="first_mission"
    ).count() == 1


@pytest.mark.django_db
def test_threshold_achievements_respect_targets():
    """Five completions unlock first+five but not the ten-mission tier."""
    user = _user()
    loc = Location.objects.create(title="Intro", description="loc")
    for i in range(5):
        m = Mission.objects.create(location=loc, title=f"M{i}", xp_reward=1)
        Progress.objects.create(user=user, mission=m, completed=True)

    newly = set(evaluate_achievements(user))
    assert {"first_mission", "five_missions"} <= newly
    assert "ten_missions" not in newly


@pytest.mark.django_db
def test_level_5_unlocks_via_profile_level():
    """Reaching level 5 earns ``level_5`` even with no missions done."""
    user = _user()
    user.profile.level = 5
    user.profile.save(update_fields=["level"])

    newly = evaluate_achievements(user)
    assert "level_5" in newly
    assert "first_mission" not in newly  # no missions completed


@pytest.mark.django_db
def test_track_complete_unlocks_when_track_cleared():
    """Clearing every active mission in a track earns ``track_complete``."""
    user = _user()
    track = Track.objects.create(title="Foundations")
    loc = Location.objects.create(
        track=track, title="World 1", description="loc"
    )
    m1 = Mission.objects.create(location=loc, title="A", xp_reward=1)
    m2 = Mission.objects.create(location=loc, title="B", xp_reward=1)
    Progress.objects.create(user=user, mission=m1, completed=True)

    # One of two missions done → track not complete yet.
    assert "track_complete" not in evaluate_achievements(user)

    Progress.objects.create(user=user, mission=m2, completed=True)
    assert "track_complete" in evaluate_achievements(user)


@pytest.mark.django_db
def test_empty_track_does_not_grant_track_complete():
    """A track with no active missions must not hand out a free achievement.

    ``Track.is_completed_by`` fails open (empty track reads as complete); the
    achievement layer guards against that so a misconfigured track can't unlock
    ``track_complete`` for everyone.
    """
    user = _user()
    Track.objects.create(title="Empty")  # no locations/missions

    assert "track_complete" not in evaluate_achievements(user)


@pytest.mark.django_db
def test_achievements_endpoint_shape_for_fresh_user():
    """GET /api/achievements/ returns the full catalog, nothing earned yet."""
    user = _user()
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/achievements/")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 6

    expected_keys = {"slug", "icon", "target", "current", "earned", "earned_at"}
    for item in items:
        assert expected_keys <= set(item.keys())
        assert item["earned"] is False
        assert item["earned_at"] is None
        # current is clamped to target so progress bars never overflow.
        assert item["current"] <= item["target"]


@pytest.mark.django_db
def test_achievements_endpoint_requires_auth():
    """Anonymous users cannot read achievements."""
    resp = APIClient().get("/api/achievements/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_achievements_for_reports_progress_and_earned_flag():
    """``achievements_for`` annotates earned status and clamps progress."""
    user = _user()
    loc = Location.objects.create(title="Intro", description="loc")
    mission = Mission.objects.create(location=loc, title="Hello", xp_reward=1)
    Progress.objects.create(user=user, mission=mission, completed=True)
    evaluate_achievements(user)

    by_slug = {a["slug"]: a for a in achievements_for(user)}
    assert by_slug["first_mission"]["earned"] is True
    assert by_slug["first_mission"]["earned_at"] is not None
    assert by_slug["first_mission"]["current"] == 1
    # five_missions: one of five → in-progress, not earned, not overflowing.
    assert by_slug["five_missions"]["earned"] is False
    assert by_slug["five_missions"]["current"] == 1


@pytest.mark.django_db
def test_complete_endpoint_returns_new_achievements():
    """Completing a mission surfaces freshly-unlocked slugs for the toast."""
    user = _user()
    loc = Location.objects.create(title="Intro", description="loc")
    mission = Mission.objects.create(location=loc, title="Hello", xp_reward=10)

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(f"/api/missions/{mission.id}/complete/")
    assert resp.status_code == 200

    body = resp.json()
    assert "new_achievements" in body
    assert "first_mission" in body["new_achievements"]

    # A second completion of the same mission unlocks nothing new.
    resp2 = client.post(f"/api/missions/{mission.id}/complete/")
    assert resp2.status_code == 200
    assert "first_mission" not in resp2.json().get("new_achievements", [])
