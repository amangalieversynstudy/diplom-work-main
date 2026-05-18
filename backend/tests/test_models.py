"""Model tests for users and game models."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_create_user_and_profile():
    """Creating a user should also create an associated profile with default XP."""
    user = User.objects.create_user(username="testuser", password="pass")
    assert user.profile is not None
    assert user.profile.xp == 0


@pytest.mark.django_db
def test_mission_and_location_models():
    """Locations and missions should be creatable and related correctly."""
    from game.models import Location, Mission

    loc = Location.objects.create(title="Intro", description="First location")
    mission = Mission.objects.create(location=loc, title="Hello", xp_reward=10)
    assert mission.location == loc
    assert mission.xp_reward == 10
