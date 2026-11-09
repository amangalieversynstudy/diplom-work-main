"""Fixes from the security check of 2026-11-09 (public repository, live Railway and Vercel)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from game.models import Location, Mission, MissionTask, Track

User = get_user_model()
BACKEND = Path(__file__).resolve().parent.parent


def _production(extra, code):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CORS_", "TEACHER_", "FRONTEND_URL"))}
    env.update(DJANGO_SETTINGS_MODULE="core.settings.production", DJANGO_SECRET_KEY="x" * 50, ALLOWED_HOSTS="api.example.com")
    env.update(extra)
    result = subprocess.run(
        [sys.executable, "-c", f"import django.conf as c; s=c.settings; print({code})"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_production_cors_is_an_exact_list_without_credentials():
    out = _production(
        {"FRONTEND_URL": "https://site.example.com/", "CORS_ALLOWED_ORIGINS": "https://preview.example.com"},
        "s.CORS_ALLOWED_ORIGINS, s.CORS_ALLOWED_ORIGIN_REGEXES, s.CORS_ALLOW_CREDENTIALS",
    )
    assert "https://diplom-work-main-frontend.vercel.app" in out
    assert "https://site.example.com'" in out and "https://preview.example.com" in out
    # no pattern over *.vercel.app: anybody could name a project to match it
    assert out.endswith("[] False")


def test_production_refuses_the_public_invite_code():
    assert _production({}, "repr(s.TEACHER_INVITE_CODE)") == "''"
    assert _production({"TEACHER_INVITE_CODE": "pilot 2026"}, "repr(s.TEACHER_INVITE_CODE)") == "''"
    assert _production({"TEACHER_INVITE_CODE": "KAFEDRA-7Q"}, "repr(s.TEACHER_INVITE_CODE)") == "'KAFEDRA-7Q'"


@pytest.mark.django_db
def test_admin_login_is_rate_limited():
    client = APIClient()
    codes = [
        client.post("/admin/login/", {"username": "root", "password": f"wrong-{n}"}).status_code
        for n in range(11)
    ]
    assert codes[:10] == [200] * 10  # the form comes back with an error
    assert codes[10] == 403


@pytest.mark.django_db
def test_a_password_reset_ends_every_session_and_refuses_common_passwords():
    user = User.objects.create_user("reader", "reader@example.com", "Old-pass-77x")
    client = APIClient()
    tokens = client.post("/api/auth/jwt/create/", {"username": "reader", "password": "Old-pass-77x"}, format="json")
    assert tokens.status_code == 200, tokens.content
    refresh = tokens.json()["refresh"]

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    weak = client.post(
        "/api/auth/password-reset-confirm/",
        {"uid": uid, "token": default_token_generator.make_token(user), "new_password": "password123"},
        format="json",
    )
    assert weak.status_code == 400

    done = client.post(
        "/api/auth/password-reset-confirm/",
        {"uid": uid, "token": default_token_generator.make_token(user), "new_password": "New-pass-88y"},
        format="json",
    )
    assert done.status_code == 200, done.content
    assert client.post("/api/auth/jwt/refresh/", {"refresh": refresh}, format="json").status_code == 401


@pytest.mark.django_db
def test_items_do_not_open_hints_of_a_draft_mission():
    user = User.objects.create_user("learner", "l@example.com", "S3cure-pass-1")
    user.profile.hint_scrolls = 3
    user.profile.save()
    track = Track.objects.create(slug="t", title="T", is_active=True, is_public=True)
    draft = Mission.objects.create(location=Location.objects.create(track=track, title="L"), title="D", is_active=False)
    task = MissionTask.objects.create(mission=draft, task_type="code", data={"hints": [{"ru": "секрет"}]})
    client = APIClient()
    client.force_authenticate(user)
    response = client.post("/api/profile/use-item/", {"item_type": "hint_scrolls", "task_id": task.pk}, format="json")
    assert "секрет" not in response.content.decode()
    user.profile.refresh_from_db()
    assert user.profile.hint_scrolls == 3


@pytest.mark.django_db
def test_display_name_is_one_line_and_not_longer_than_the_column():
    user = User.objects.create_user("named", "n@example.com", "S3cure-pass-1")
    client = APIClient()
    client.force_authenticate(user)
    assert client.patch("/api/profile/me/", {"display_name": "x" * 151}, format="json").status_code == 400
    ok = client.patch("/api/profile/me/", {"display_name": "  Ерсін\n\tА.  "}, format="json")
    assert ok.status_code == 200
    user.refresh_from_db()
    assert user.display_name == "Ерсін А."
