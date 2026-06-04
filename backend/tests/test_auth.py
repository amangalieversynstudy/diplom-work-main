"""Tests for authentication endpoints."""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_login_logout():
    """Register a user, verify email, obtain JWT, then logout."""
    from django.contrib.auth import get_user_model
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    client = APIClient()
    register_url = "/api/auth/register/"
    login_url = "/api/auth/login/"
    logout_url = "/api/auth/logout/"

    # 1. Register — аккаунт создаётся с is_active=False
    resp = client.post(
        register_url,
        {"username": "u1", "password": "TestPass123!", "email": "u1@example.com"},
    )
    assert resp.status_code == 201

    # 2. Логин неактивного пользователя с ВЕРНЫМ паролем → 403 + code,
    #    чтобы фронт показал баннер «переотправить активацию».
    resp = client.post(login_url, {"username": "u1", "password": "TestPass123!"})
    assert resp.status_code == 403
    assert resp.json().get("code") == "account_inactive"

    # 2b. Неверный пароль НЕ должен палить статус активации — обычный 401.
    resp = client.post(login_url, {"username": "u1", "password": "WrongPass999!"})
    assert resp.status_code == 401

    # 3. Активация email
    User = get_user_model()
    user = User.objects.get(username="u1")
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    resp = client.get(f"/api/auth/verify-email/?uid={uid}&token={token}")
    assert resp.status_code == 200

    # 4. Теперь логин проходит
    resp = client.post(login_url, {"username": "u1", "password": "TestPass123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access" in data and "refresh" in data

    # 5. Logout (blacklist refresh)
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
        {"username": "u2", "password": "TestPass456!", "email": "u2@example.com"},
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


@pytest.mark.django_db
def test_email_change_requires_confirmation():
    """Changing the profile email is deferred until the confirm link is opened.

    The new address is not written immediately — the old one stays active so a
    typo can never lock the account out. PATCH returns ``email_change_pending``;
    only opening the signed link (same token as the email carries) applies it.
    """
    from django.contrib.auth import get_user_model
    from django.core import signing

    User = get_user_model()
    user = User.objects.create_user(
        username="changer", password="TestPass123!", email="old@example.com"
    )
    user.is_active = True
    user.save(update_fields=["is_active"])

    client = APIClient()
    client.force_authenticate(user=user)

    # PATCH new email → pending; БД не меняется.
    resp = client.patch(
        "/api/profile/me/", {"email": "new@example.com"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json().get("email_change_pending") == "new@example.com"
    user.refresh_from_db()
    assert user.email == "old@example.com"

    # Открываем ссылку-подтверждение → адрес применяется.
    token = signing.dumps(
        {"uid": user.pk, "email": "new@example.com"}, salt="email-change"
    )
    resp = client.get("/api/auth/confirm-email/", {"token": token})
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.email == "new@example.com"


@pytest.mark.django_db
def test_confirm_email_rejects_bad_token():
    """A garbage/tampered confirmation token is rejected with 400, no change."""
    client = APIClient()
    resp = client.get("/api/auth/confirm-email/", {"token": "not-a-real-token"})
    assert resp.status_code == 400
