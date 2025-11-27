"""Tests for profile API endpoints."""

import pytest
from django.contrib.auth import get_user_model
from game.models import ClassRole
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_profile_requires_authentication():
    client = APIClient()
    resp = client.get("/api/profile")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_profile_get_and_patch_once():
    user = get_user_model().objects.create_user(username="hero", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)

    # initial GET
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 1
    assert data["class_role"] is None

    # first PATCH allows selecting a class and updating bio
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

    # second PATCH attempting to change class should fail
    mage = ClassRole.objects.create(name="Mage")
    resp = client.patch(
        "/api/profile",
        {"class_role": mage.id},
        format="json",
    )
    assert resp.status_code == 400
    assert "Class role can be selected only once" in resp.json()["class_role"][0]

    # cannot reset to null either
    resp = client.patch(
        "/api/profile",
        {"class_role": None},
        format="json",
    )
    assert resp.status_code == 400
