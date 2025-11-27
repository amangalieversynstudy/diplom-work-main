"""Tests for signal handlers (e.g., profile creation)."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_profile_created_on_user_creation():
    """User creation should trigger creation of a Profile with defaults."""
    u = User.objects.create_user(username="signal_user", password="pw")
    assert hasattr(u, "profile")
    assert u.profile.xp == 0
    assert u.profile.level == 1
