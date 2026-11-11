"""Flags the client needs to stay honest: is the AI mentor configured, did a verification letter really go out."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"


def _login(username="flaguser"):
    user = User.objects.create_user(username=username, password=PASSWORD)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_profile_reports_mentor_unavailable_without_key(settings, monkeypatch):
    settings.GEMINI_API_KEY = ""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert _login().get("/api/profile/me/").json()["mentor_available"] is False


def test_profile_reports_mentor_available_with_key(settings):
    settings.GEMINI_API_KEY = "test-key"
    assert _login("flaguser2").get("/api/profile/me/").json()["mentor_available"] is True


def test_register_says_no_letter_was_sent_with_console_mail(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    response = APIClient().post(
        "/api/auth/register/",
        {"username": "flagreg", "email": "flagreg@example.com", "password": PASSWORD, "role": "student"},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["verification_email_sent"] is False
    assert User.objects.get(username="flagreg").is_active is True
