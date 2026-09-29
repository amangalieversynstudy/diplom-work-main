"""Account-security regressions from the security scan (F4, F9, F10, F13, F15, F16)."""

import itertools

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from game import runner
from users.tokens import email_verification_token

User = get_user_model()

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass123!"


def _uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def _signed_in(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def _register(api, username, email="", password=PASSWORD):
    return api.post(
        "/api/auth/register/", {"username": username, "email": email, "password": password}
    )


# ── F4: reset links go to the stored address ────────────────────────────────


def test_reset_mail_goes_to_the_stored_address_not_the_typed_one():
    User.objects.create_user("teacher", "Teacher@School.example", PASSWORD)
    response = APIClient().post(
        "/api/auth/password-reset/", {"email": "teacher@school.example"}
    )
    assert response.status_code == 200
    assert [m.to for m in mail.outbox] == [["Teacher@school.example"]]


def test_reset_is_not_sent_to_blocked_or_unknown_accounts_and_answers_alike():
    User.objects.create_user("blocked", "blocked@x.example", PASSWORD, is_active=False)
    api = APIClient()
    known = api.post("/api/auth/password-reset/", {"email": "blocked@x.example"})
    unknown = api.post("/api/auth/password-reset/", {"email": "nobody@x.example"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert mail.outbox == []


def test_lookalike_addresses_are_not_matched():
    from users.views_password import _fold

    assert _fold("Teacher@School.EXAMPLE") == _fold("teacher@school.example")
    assert _fold("teacher@gmaıl.com") != _fold("teacher@gmail.com")  # dotless i


# ── F13: activation and reset links are not interchangeable ─────────────────


def _pending_user(name="newbie", email="newbie@x.example"):
    user = User.objects.create_user(name, email, PASSWORD, is_active=False)
    user.email_verification_pending = True
    user.save(update_fields=["email_verification_pending"])
    return user


def _verify(api, user, token):
    return api.get(f"/api/auth/verify-email/?uid={_uid(user)}&token={token}")


def test_a_password_reset_token_does_not_activate_an_account():
    user = _pending_user()
    response = _verify(APIClient(), user, default_token_generator.make_token(user))
    assert response.status_code == 400
    user.refresh_from_db()
    assert not user.is_active


def test_an_activation_token_cannot_reset_a_password():
    user = _pending_user()
    response = APIClient().post(
        "/api/auth/password-reset-confirm/",
        {
            "uid": _uid(user),
            "token": email_verification_token.make_token(user),
            "new_password": "Attacker-pass-1",
        },
        format="json",
    )
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


def test_an_activation_link_dies_after_use():
    user = _pending_user()
    token = email_verification_token.make_token(user)
    api = APIClient()
    assert _verify(api, user, token).status_code == 200
    user.refresh_from_db()
    assert user.is_active and not user.email_verification_pending
    assert _verify(api, user, token).status_code == 400


# ── F15: a block by an administrator is not undone by e-mail ────────────────


def test_registration_waits_for_the_link_and_the_link_activates():
    api = APIClient()
    assert _register(api, "waiter", "waiter@x.example").status_code == 201
    user = User.objects.get(username="waiter")
    assert not user.is_active and user.email_verification_pending
    assert len(mail.outbox) == 1

    assert _verify(api, user, email_verification_token.make_token(user)).status_code == 200
    user.refresh_from_db()
    assert user.is_active and not user.email_verification_pending


def test_a_blocked_account_cannot_reactivate_itself():
    user = User.objects.create_user("banned", "banned@x.example", PASSWORD)
    user.is_active = False  # what an admin does; nothing is pending
    user.save()
    api = APIClient()

    assert _verify(api, user, email_verification_token.make_token(user)).status_code == 400
    api.post("/api/auth/resend-verification/", {"email": "banned@x.example"})
    assert mail.outbox == []
    user.refresh_from_db()
    assert not user.is_active


def test_only_a_waiting_account_gets_the_activation_banner_at_login():
    api = APIClient()
    _pending_user("waiting", "waiting@x.example")
    banned = User.objects.create_user("banned", "banned@x.example", PASSWORD)
    banned.is_active = False
    banned.save()

    waiting = api.post("/api/auth/login/", {"username": "waiting", "password": PASSWORD})
    assert waiting.status_code == 403 and waiting.json()["code"] == "account_inactive"
    refused = api.post("/api/auth/login/", {"username": "banned", "password": PASSWORD})
    assert refused.status_code == 401


# ── F16: login identifiers cannot be hijacked ───────────────────────────────


def test_usernames_cannot_look_like_addresses():
    response = _register(APIClient(), "victim@school.example")
    assert response.status_code == 400 and "username" in response.json()


def test_usernames_are_unique_regardless_of_case():
    api = APIClient()
    assert _register(api, "Alice").status_code == 201
    assert _register(api, "alice").status_code == 400


def test_an_old_username_equal_to_an_address_does_not_capture_that_address():
    victim = User.objects.create_user("victim", "victim@school.example", PASSWORD)
    User.objects.create_user("victim@school.example", "squatter@x.example", "Squatter-pass-1")
    response = APIClient().post(
        "/api/auth/login/", {"username": "victim@school.example", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert User.objects.get(pk=victim.pk).username == "victim"


def test_login_still_works_with_username_or_email_in_any_case():
    User.objects.create_user("Sam", "sam@x.example", PASSWORD)
    api = APIClient()
    for identifier in ("sam", "SAM", "sam@x.example", "Sam@X.Example"):
        response = api.post("/api/auth/login/", {"username": identifier, "password": PASSWORD})
        assert response.status_code == 200, identifier


def test_the_profile_cannot_take_an_address_shaped_username():
    user = User.objects.create_user("plain", "plain@x.example", PASSWORD)
    response = _signed_in(user).patch(
        "/api/profile/me/", {"username": "someone@else.example"}, format="json"
    )
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.username == "plain"


# ── F10: an e-mail change goes to exactly one valid address ─────────────────


@pytest.mark.parametrize(
    "typed",
    ["a@x.example,b@y.example", "a@x.example b@y.example", "a@x.example;b@y.example",
     "a@x.example\nb@y.example", "not-an-address"],
)
def test_email_change_rejects_lists_and_junk(typed):
    user = User.objects.create_user("changer", "old@x.example", PASSWORD)
    response = _signed_in(user).patch("/api/profile/me/", {"email": typed}, format="json")
    assert response.status_code == 400
    assert mail.outbox == []


def test_email_change_sends_one_message_to_one_address():
    user = User.objects.create_user("changer", "old@x.example", PASSWORD)
    response = _signed_in(user).patch(
        "/api/profile/me/", {"email": "New@X.example"}, format="json"
    )
    assert response.status_code == 200
    assert [m.to for m in mail.outbox] == [["new@x.example"]]


@pytest.mark.parametrize("name", ["Click http://evil.example now", "line\nbreak", "tab\there"])
def test_usernames_cannot_carry_text(name):
    user = User.objects.create_user("plain", "plain@x.example", PASSWORD)
    response = _signed_in(user).patch("/api/profile/me/", {"username": name}, format="json")
    assert response.status_code == 400


def test_email_changes_are_rate_limited():
    user = User.objects.create_user("changer", "old@x.example", PASSWORD)
    api = _signed_in(user)
    counter = itertools.count()
    statuses = [
        api.patch("/api/profile/me/", {"email": f"n{next(counter)}@x.example"}, format="json").status_code
        for _ in range(7)
    ]
    assert statuses[:5] == [200] * 5
    assert statuses[5:] == [429, 429]
    assert len(mail.outbox) == 5


# ── F9: container logs are read with a cap ──────────────────────────────────


class _FakeContainer:
    def __init__(self, chunks):
        self._chunks = chunks
        self.stream_closed = False
        self.calls = []

    def logs(self, **kwargs):
        self.calls.append(kwargs)
        outer = self

        def generate():
            try:
                yield from outer._chunks
            finally:
                outer.stream_closed = True

        return generate()


def test_flooding_logs_are_cut_without_reading_everything():
    read = []

    def flood():
        for _ in range(10_000):  # would be ~10 GB if read to the end
            read.append(1)
            yield b"x" * 1_000_000

    container = _FakeContainer(flood())
    data = runner._read_capped_logs(container)
    assert container.calls[0]["stream"] is True
    assert len(read) == 1  # stopped at the first chunk that crossed the limit
    assert data.startswith(b"x" * runner.MAX_OUTPUT_SIZE)
    assert len(data) < runner.MAX_OUTPUT_SIZE + 100
    assert data.endswith("[ВЫВОД ОБРЕЗАН] ...".encode("utf-8"))


def test_short_and_exact_limit_output_is_not_marked_truncated():
    assert runner._read_capped_logs(_FakeContainer([b"hello ", b"world"])) == b"hello world"
    exact = _FakeContainer([b"y" * runner.MAX_OUTPUT_SIZE])
    assert runner._read_capped_logs(exact) == b"y" * runner.MAX_OUTPUT_SIZE


def test_the_container_journal_itself_is_capped():
    config = runner._SANDBOX_KWARGS["log_config"]
    assert config["Config"]["max-size"] == "1m" and config["Config"]["max-file"] == "1"
