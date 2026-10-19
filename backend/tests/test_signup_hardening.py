"""Sign-up and login hardening: 429 for rate limits, the teacher e-mail rule, adding a first e-mail,
the username race, blocked accounts on the WebSocket, learners' records in the admin."""

import re

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
REGISTER = "/api/auth/register/"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _signup(name, role="student", **extra):
    return APIClient().post(REGISTER, {"username": name, "password": "HardPass123!", "role": role, **extra})


@pytest.mark.django_db
def test_a_rate_limit_is_a_429_with_a_readable_message():
    client = APIClient()
    codes = []
    for i in range(12):
        codes.append(client.post("/api/auth/login/", {"username": "nobody", "password": f"x{i}"}).status_code)
    assert 429 in codes
    blocked = client.post("/api/auth/login/", {"username": "nobody", "password": "x"})
    assert blocked.status_code == 429 and "попыток" in blocked.json()["detail"]


@pytest.mark.django_db
@override_settings(TEACHER_REQUIRE_EMAIL=True, DEBUG=False, EMAIL_BACKEND=LOCMEM)
def test_a_teacher_needs_an_email_when_mail_really_goes_out():
    response = _signup("t_noemail", role="teacher")
    assert response.status_code == 400 and "email" in response.json()
    assert not User.objects.filter(username="t_noemail").exists()

    response = _signup("t_email", role="teacher", email="teacher@example.com")
    assert response.status_code == 201
    teacher = User.objects.get(username="t_email")
    assert teacher.is_teacher and not teacher.is_active and teacher.email_verification_pending
    assert len(mail.outbox) == 1
    # a learner is not affected
    assert _signup("s_noemail").status_code == 201


@pytest.mark.django_db
@override_settings(TEACHER_REQUIRE_EMAIL=True, DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
def test_the_teacher_email_rule_is_skipped_when_mail_cannot_be_sent():
    assert _signup("t_console", role="teacher").status_code == 201
    assert User.objects.get(username="t_console").is_active


@pytest.mark.django_db
@override_settings(TEACHER_REQUIRE_EMAIL=True, DEBUG=False, EMAIL_BACKEND=LOCMEM)
def test_a_teacher_cannot_remove_the_email_while_the_rule_is_on():
    teacher = User.objects.create_user(username="t_keep", password="x", email="keep@example.com", is_teacher=True)
    client = APIClient()
    client.force_authenticate(teacher)
    assert client.patch("/api/profile/me/", {"email": ""}, format="json").status_code == 400
    teacher.refresh_from_db()
    assert teacher.email == "keep@example.com"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_an_account_without_email_can_add_one():
    user = User.objects.create_user(username="no_mail", password="x", email="")
    client = APIClient()
    client.force_authenticate(user)
    assert client.patch("/api/profile/me/", {"email": "new@example.com"}, format="json").status_code == 200
    link = re.search(r"token=([\w\-.:]+)", mail.outbox[-1].body)
    assert link, mail.outbox[-1].body
    token = link.group(1)
    assert APIClient().get("/api/auth/confirm-email/", {"token": token}).status_code == 200
    user.refresh_from_db()
    assert user.email == "new@example.com"
    assert APIClient().get("/api/auth/confirm-email/", {"token": token}).status_code == 400  # single use


@pytest.mark.django_db
def test_a_parallel_sign_up_with_the_same_name_is_a_400(monkeypatch):
    from users import serializers_auth

    User.objects.create_user(username="twin", password="x")
    real_filter = User.objects.filter

    def blind_filter(*args, **kwargs):
        if "username__iexact" in kwargs:
            return real_filter(pk__in=[])
        return real_filter(*args, **kwargs)

    monkeypatch.setattr(serializers_auth.User.objects, "filter", blind_filter)
    response = _signup("twin")
    assert response.status_code == 400 and "username" in response.json()


@pytest.mark.django_db
def test_a_blocked_account_is_anonymous_on_the_websocket():
    from core.middleware import _resolve_user

    user = User.objects.create_user(username="ws_blocked", password="x")
    token = str(AccessToken.for_user(user))
    assert async_to_sync(_resolve_user)(token) == user
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert isinstance(async_to_sync(_resolve_user)(token), AnonymousUser)


@pytest.mark.django_db
def test_learners_records_in_the_admin_are_for_superusers_only():
    staff = User.objects.create_user(username="adm_staff", password="x", is_staff=True)
    staff.user_permissions.add(*Permission.objects.filter(codename__in=["view_progress", "view_coderun"]))
    client = APIClient()
    client.force_login(staff)
    assert client.get("/admin/game/progress/").status_code in (302, 403)
    assert client.get("/admin/game/coderun/").status_code in (302, 403)
    root = User.objects.create_user(username="adm_root", password="x", is_staff=True, is_superuser=True)
    client.force_login(root)
    assert client.get("/admin/game/progress/").status_code == 200


@pytest.mark.django_db
def test_json_logins_of_different_people_do_not_share_one_limit():
    """The per-account login limit reads JSON bodies: a class logging in together is not blocked."""
    for i in range(15):
        User.objects.create_user(username=f"pupil_{i}", password="HardPass123!")
    codes = [
        APIClient().post(
            "/api/auth/login/", {"username": f"pupil_{i}", "password": "HardPass123!"}, format="json",
            REMOTE_ADDR=f"10.1.0.{i}",
        ).status_code
        for i in range(15)
    ]
    assert codes == [200] * 15


@pytest.mark.django_db
def test_one_account_is_limited_whatever_the_address():
    User.objects.create_user(username="target", password="HardPass123!")
    codes = [
        APIClient().post(
            "/api/auth/login/", {"username": "target", "password": f"wrong{i}"}, format="json",
            REMOTE_ADDR=f"10.2.0.{i}",
        ).status_code
        for i in range(12)
    ]
    assert codes[-1] == 429


@pytest.mark.django_db
def test_a_forged_forwarded_for_header_neither_bypasses_limits_nor_breaks_sign_up():
    response = APIClient().post(
        REGISTER, {"username": "xff_user", "password": "HardPass123!"}, HTTP_X_FORWARDED_FOR="a, b, not-an-ip"
    )
    assert response.status_code == 201
