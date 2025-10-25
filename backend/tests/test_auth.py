"""Tests for authentication endpoints."""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_login_logout():
    """Register a user, obtain tokens via login, and logout (blacklist refresh)."""
    client = APIClient()
    register_url = "/api/auth/register/"
    login_url = "/api/auth/login/"
    logout_url = "/api/auth/logout/"

    # Register
    resp = client.post(register_url, {"username": "u1", "password": "p1"})
    assert resp.status_code == 201

    # Login
    resp = client.post(login_url, {"username": "u1", "password": "p1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access" in data and "refresh" in data

    # Logout (blacklist refresh)
    refresh = data["refresh"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
    resp = client.post(logout_url, {"refresh": refresh})
    assert resp.status_code in (205, 200)


@pytest.mark.django_db
def test_register_and_verify_email(client):
    """Register and simulate email verification for the registered user."""
    # register user
    resp = client.post(
        "/api/auth/register/",
        {"username": "u2", "password": "p2", "email": "u2@example.com"},
    )
    assert resp.status_code == 201
    # since email backend is console, we can't read it here; instead, ensure user exists and is_active flag
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = User.objects.get(username="u2")
    # by default user created may be inactive until verification
    # simulate verification by calling the verify endpoint with token
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(u.pk))
    token = default_token_generator.make_token(u)
    verify_path = f"/api/auth/verify-email/?uid={uid}&token={token}"
    resp = client.get(verify_path)
    assert resp.status_code == 200
