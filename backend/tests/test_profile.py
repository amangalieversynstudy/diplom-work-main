"""Tests for profile API endpoints."""

import pytest
from django.contrib.auth import get_user_model
from game.models import ClassRole, Rank
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_profile_requires_authentication():
    client = APIClient()
    resp = client.get("/api/profile")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_profile_get_and_change_class_freely():
    user = get_user_model().objects.create_user(username="hero", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)

    # initial GET
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 1
    assert data["class_role"] is None

    # first PATCH selects a class and updates bio
    warrior = ClassRole.objects.create(name="Warrior")
    resp = client.patch(
        "/api/profile",
        {"bio": "Ready to learn", "class_role": warrior.id},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bio"] == "Ready to learn"
    assert data["class_role"] == warrior.id

    # by design the class is NOT locked: the player may switch paths at any
    # time (see users/serializers.py + frontend/pages/class.jsx), so a second
    # PATCH that changes the class must succeed.
    mage = ClassRole.objects.create(name="Mage")
    resp = client.patch(
        "/api/profile",
        {"class_role": mage.id},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["class_role"] == mage.id

    # and it may be cleared back to null
    resp = client.patch(
        "/api/profile",
        {"class_role": None},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["class_role"] is None


@pytest.mark.django_db
def test_profile_rank_display_tc_rank_01():
    """TC-RANK-01: Verify rank chip displays and updates on profile.

    Tests that:
    1. Profile endpoint returns rank data when user qualifies
    2. Rank is correctly calculated based on level/xp thresholds
    3. Rank updates when user levels up
    """
    User = get_user_model()
    user = User.objects.create_user(username="hero", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)

    # Create ranks with specific thresholds
    apprentice = Rank.objects.create(
        slug="apprentice",
        title_ru="Ученик",
        title_en="Apprentice",
        min_level=1,
        min_xp=0,
    )
    veteran = Rank.objects.create(
        slug="veteran",
        title_ru="Ветеран",
        title_en="Veteran",
        min_level=3,
        min_xp=200,
    )

    # Initially, user should have apprentice rank (level 1, xp 0)
    resp = client.get("/api/profile/me/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 1
    assert data["rank"] is not None
    assert data["rank"]["slug"] == "apprentice"
    assert data["rank"]["title_ru"] == "Ученик"

    # Level up the user to level 3 with enough xp
    user.profile.xp = 250  # 250 XP = level 3 (250 // 100 + 1)
    user.profile.level = 3
    user.profile.save()

    # Now user should have veteran rank
    resp = client.get("/api/profile/me/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 3
    assert data["xp"] == 250
    assert data["rank"] is not None
    assert data["rank"]["slug"] == "veteran"
    assert data["rank"]["title_ru"] == "Ветеран"
