"""Tests for teacher self-registration via an invite code.

A correct ``teacher_code`` at registration grants ``is_staff`` (teacher access:
analytics + the teacher cabinet). The code is a shared server secret
(``settings.TEACHER_INVITE_CODE``); an empty secret disables teacher
registration entirely so no one can gain staff through the public endpoint.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

User = get_user_model()

REGISTER_URL = "/api/auth/register/"
CODE = "SECRET-TEACH"


@pytest.fixture(autouse=True)
def _reset_ratelimit_cache():
    """Give each test a fresh rate-limit budget.

    RegisterView is throttled 5/min per IP via django-ratelimit, whose counter
    lives in the cache. Under the test settings the cache is a process-wide
    LocMemCache, so the counter leaks across tests and later registrations get
    blocked (403). Clearing it around each test keeps them isolated.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE=CODE)
def test_valid_teacher_code_grants_staff():
    """A correct invite code creates a teacher (is_staff=True)."""
    client = APIClient()
    resp = client.post(
        REGISTER_URL,
        {
            "username": "teacher1",
            "password": "TeachPass123!",
            "email": "teacher1@example.com",
            "teacher_code": CODE,
        },
    )
    assert resp.status_code == 201
    user = User.objects.get(username="teacher1")
    assert user.is_staff is True
    # The code must never leak back in the response.
    assert "teacher_code" not in resp.json()


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE=CODE)
def test_wrong_teacher_code_is_rejected():
    """A wrong code is a 400 and creates no account at all."""
    client = APIClient()
    resp = client.post(
        REGISTER_URL,
        {
            "username": "imposter",
            "password": "TeachPass123!",
            "email": "imposter@example.com",
            "teacher_code": "WRONG-CODE",
        },
    )
    assert resp.status_code == 400
    assert "teacher_code" in resp.json()
    assert not User.objects.filter(username="imposter").exists()


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE=CODE)
def test_no_teacher_code_creates_regular_student():
    """Omitting the code (the normal path) yields a non-staff student."""
    client = APIClient()
    resp = client.post(
        REGISTER_URL,
        {
            "username": "student1",
            "password": "TeachPass123!",
            "email": "student1@example.com",
        },
    )
    assert resp.status_code == 201
    user = User.objects.get(username="student1")
    assert user.is_staff is False


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE=CODE)
def test_blank_teacher_code_creates_regular_student():
    """An empty string code is treated as 'no code' — a normal student."""
    client = APIClient()
    resp = client.post(
        REGISTER_URL,
        {
            "username": "student2",
            "password": "TeachPass123!",
            "email": "student2@example.com",
            "teacher_code": "",
        },
    )
    assert resp.status_code == 201
    assert User.objects.get(username="student2").is_staff is False


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE="")
def test_teacher_registration_disabled_when_secret_unset():
    """With no server secret configured, any supplied code is rejected.

    This is the fail-closed default: teacher registration must be explicitly
    enabled via env, otherwise a leaked/guessed code can't mint staff accounts.
    """
    client = APIClient()
    resp = client.post(
        REGISTER_URL,
        {
            "username": "ghost",
            "password": "TeachPass123!",
            "email": "ghost@example.com",
            "teacher_code": "anything",
        },
    )
    assert resp.status_code == 400
    assert not User.objects.filter(username="ghost").exists()
