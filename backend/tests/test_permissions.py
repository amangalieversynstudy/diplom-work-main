"""Access-control regression tests.

The API is closed to anonymous users by default (``DEFAULT_PERMISSION_CLASSES``)
and every public endpoint has to opt in explicitly. These tests pin both sides:
the generic users endpoint must not exist, protected routes must answer 401 to
anonymous callers, and the intentionally public routes must stay reachable.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def victim():
    return User.objects.create_user(
        "victim", "victim@example.com", "S3cure-pass-1", display_name="Victim"
    )


@pytest.fixture
def student():
    return User.objects.create_user("student", "student@example.com", "S3cure-pass-2")


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# ── /api/users/ must not exist ──────────────────────────────────────────────


@pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
def test_users_collection_is_not_exposed_to_anonymous(anon, victim, method):
    response = getattr(anon, method)("/api/users/", {}, format="json")
    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_user_detail_is_not_exposed_to_anonymous(anon, victim, method):
    response = getattr(anon, method)(
        f"/api/users/{victim.id}/", {"email": "evil@example.com"}, format="json"
    )
    assert response.status_code == 404
    victim.refresh_from_db()
    assert victim.email == "victim@example.com"


def test_logged_in_student_cannot_touch_other_users(student, victim):
    client = _client_for(student)
    assert client.get("/api/users/").status_code == 404
    assert client.delete(f"/api/users/{victim.id}/").status_code == 404
    assert User.objects.filter(pk=victim.pk).exists()


# ── secure by default ───────────────────────────────────────────────────────


def test_default_permission_class_is_authenticated(settings):
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == (
        "rest_framework.permissions.IsAuthenticated",
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/progress/",
        "/api/task-progress/",
        "/api/profile/me/",
        "/api/intro-status/",
        "/api/achievements/",
        "/api/analytics/",
        "/api/teacher/students/",
        "/api/teacher/studio/tracks/",
        "/api/auth/me/",
    ],
)
def test_protected_endpoints_reject_anonymous(anon, path):
    assert anon.get(path).status_code in (401, 403)


@pytest.mark.parametrize(
    "path", ["/api/tracks/", "/api/ranks/", "/api/leaderboard/", "/api/missions/"]
)
def test_public_catalogue_stays_readable_anonymously(anon, path):
    assert anon.get(path).status_code == 200


def test_healthcheck_stays_public(anon):
    assert anon.get("/healthz").status_code == 200


# ── auth flows must keep working without a token ────────────────────────────


def test_registration_is_reachable_anonymously(anon):
    response = anon.post(
        "/api/auth/register/",
        {"username": "newbie", "email": "newbie@example.com", "password": "S3cure-pass-3"},
        format="json",
    )
    assert response.status_code == 201


def test_login_is_reachable_anonymously(anon, victim):
    response = anon.post(
        "/api/auth/login/",
        {"username": "victim", "password": "S3cure-pass-1"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.json()


def test_password_reset_request_is_public_and_does_not_leak_accounts(anon, victim):
    known = anon.post(
        "/api/auth/password-reset/", {"email": "victim@example.com"}, format="json"
    )
    unknown = anon.post(
        "/api/auth/password-reset/", {"email": "nobody@example.com"}, format="json"
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_password_reset_confirm_is_public_but_rejects_bad_token(anon, victim):
    response = anon.post(
        "/api/auth/password-reset-confirm/",
        {"uid": "MQ", "token": "bad-token", "new_password": "An0ther-pass-1"},
        format="json",
    )
    assert response.status_code == 400
    victim.refresh_from_db()
    assert victim.check_password("S3cure-pass-1")


def test_email_verification_endpoints_are_public(anon):
    assert anon.get("/api/auth/verify-email/").status_code == 400
    assert anon.get("/api/auth/confirm-email/").status_code == 400
    response = anon.post("/api/auth/resend-verification/", {"email": ""}, format="json")
    assert response.status_code == 200


@override_settings(TEACHER_INVITE_CODE="")
def test_anonymous_cannot_become_teacher_without_configured_code(anon):
    response = anon.post(
        "/api/auth/register/",
        {
            "username": "wannabe",
            "email": "wannabe@example.com",
            "password": "S3cure-pass-4",
            "teacher_code": "RPG-TEACHER-2026",
        },
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(username="wannabe").exists()
