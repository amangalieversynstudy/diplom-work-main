"""Tests for teacher self-registration via an invite code.

A correct ``teacher_code`` at registration grants the self-service teacher role (``is_teacher``: own courses and
classes only), never ``is_staff``. The code is ``settings.TEACHER_INVITE_CODE``; a switched-off (empty) code
rejects every code, so nobody becomes a teacher through the public endpoint by guessing.
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
def test_valid_teacher_code_grants_the_teacher_role_not_staff():
    """A correct invite code creates a self-service teacher: the cabinet, never the admin."""
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
    assert (user.is_teacher, user.is_staff, user.can_teach) == (True, False, True)
    # The code must never leak back in the response.
    assert "teacher_code" not in resp.json()


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE=CODE, TEACHER_SELF_REGISTRATION=False)
def test_code_typed_by_hand_matches_and_opens_closed_sign_up():
    """Case, spaces and dashes do not matter; with the code a closed teacher sign-up still works."""
    resp = APIClient().post(
        REGISTER_URL,
        {"username": "teacher2", "password": "TeachPass123!", "role": "teacher", "teacher_code": " secret teach "},
    )
    assert resp.status_code == 201
    assert User.objects.get(username="teacher2").is_teacher is True


@pytest.mark.django_db
@override_settings(TEACHER_INVITE_CODE=CODE)
def test_a_non_ascii_code_is_a_clean_400_not_a_500():
    resp = APIClient().post(
        REGISTER_URL, {"username": "kirill", "password": "TeachPass123!", "teacher_code": "КОД-УЧИТЕЛЯ"}
    )
    assert resp.status_code == 400
    assert "teacher_code" in resp.json()


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


def _invite_code_with(env_value):
    """TEACHER_INVITE_CODE as the base settings read it, in a fresh interpreter (None = variable unset)."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {k: v for k, v in os.environ.items() if k != "TEACHER_INVITE_CODE"}
    if env_value is not None:
        env["TEACHER_INVITE_CODE"] = env_value
    code = "import core.settings.base as b; print(repr(b.TEACHER_INVITE_CODE))"
    backend = Path(__file__).resolve().parent.parent
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return eval(out.stdout.strip())  # noqa: S307 - our own repr of a str


def test_invite_code_default_off_switch_and_own_value():
    """Unset = the pilot default; "off" switches the code off; an own value is used as typed (trimmed)."""
    assert _invite_code_with(None) == "PILOT-2026"
    assert _invite_code_with("off") == ""
    assert _invite_code_with("  MY-OWN-CODE ") == "MY-OWN-CODE"
