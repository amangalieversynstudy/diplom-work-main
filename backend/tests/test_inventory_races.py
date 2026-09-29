"""Spending inventory items must be atomic (audit C4)."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from users.models import Profile

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(username="learner", password="TestPass123!")


def _api(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def _set(user, **fields):
    Profile.objects.filter(user=user).update(**fields)


# ── use_item / refund_item ──────────────────────────────────────────────────


def test_two_stale_copies_cannot_spend_the_same_scroll():
    """The old read-modify-write let both callers "succeed" with one scroll left."""
    user = User.objects.create_user(username="racer", password="x" * 12)
    _set(user, hint_scrolls=1)
    first = Profile.objects.get(user=user)
    second = Profile.objects.get(user=user)  # loaded before the first spends

    assert first.use_item("hint_scrolls") is True
    assert second.use_item("hint_scrolls") is False
    assert Profile.objects.get(user=user).hint_scrolls == 0
    assert second.hint_scrolls == 0  # the stale copy learns the truth


def test_the_count_never_goes_negative_and_unknown_items_are_refused(user):
    profile = Profile.objects.get(user=user)
    _set(user, skeleton_scrolls=0)
    profile.refresh_from_db()
    assert profile.use_item("skeleton_scrolls") is False
    assert Profile.objects.get(user=user).skeleton_scrolls == 0
    for name in ("xp", "level", "user", "__class__", "nonsense"):
        assert profile.use_item(name) is False


def test_spending_decrements_by_exactly_one(user):
    _set(user, hint_scrolls=5)
    profile = Profile.objects.get(user=user)
    assert profile.use_item("hint_scrolls") is True
    assert profile.hint_scrolls == 4
    assert Profile.objects.get(user=user).hint_scrolls == 4


def test_refund_puts_the_item_back_and_ignores_unknown_names(user):
    _set(user, ai_summons=2)
    profile = Profile.objects.get(user=user)
    profile.use_item("ai_summons")
    profile.refund_item("ai_summons")
    profile.refund_item("xp")
    assert Profile.objects.get(user=user).ai_summons == 2
    assert Profile.objects.get(user=user).xp == profile.xp


# ── the endpoint people click ───────────────────────────────────────────────


def test_use_item_endpoint_spends_once_and_then_refuses(user):
    _set(user, hint_scrolls=1)
    api = _api(user)
    ok = api.post("/api/profile/use-item/", {"item_type": "hint_scrolls"}, format="json")
    assert ok.status_code == 200 and ok.json()["remaining"] == 0
    again = api.post("/api/profile/use-item/", {"item_type": "hint_scrolls"}, format="json")
    assert again.status_code == 400


# ── AI: reserve first, refund when nothing was delivered ────────────────────


ENDPOINTS = [
    ("/api/ai-assist/", "game.views.AIAssistView._call_gemini", {"task_description": "t"}),
    ("/api/ai-mentor/", "game.views._call_gemini_chat", {"messages": [{"role": "user", "content": "help"}]}),
]


@pytest.mark.parametrize("url, target, body", ENDPOINTS)
def test_a_delivered_answer_costs_one_summon(user, url, target, body):
    _set(user, ai_summons=1)
    with patch(target, return_value=("answer", True)):
        response = _api(user).post(url, body, format="json")
    assert response.status_code == 200
    assert response.json()["remaining_summons"] == 0
    assert Profile.objects.get(user=user).ai_summons == 0


@pytest.mark.parametrize("url, target, body", ENDPOINTS)
def test_a_failed_ai_call_costs_nothing(user, url, target, body):
    _set(user, ai_summons=1)
    with patch(target, return_value=("AI is down", False)):
        response = _api(user).post(url, body, format="json")
    assert response.status_code == 200
    assert response.json()["remaining_summons"] == 1
    assert Profile.objects.get(user=user).ai_summons == 1


@pytest.mark.parametrize("url, target, body", ENDPOINTS)
def test_a_crash_inside_the_ai_call_refunds_the_summon(user, url, target, body):
    _set(user, ai_summons=1)
    api = _api(user)
    api.raise_request_exception = False
    with patch(target, side_effect=RuntimeError("boom")):
        response = api.post(url, body, format="json")
    assert response.status_code == 500
    assert Profile.objects.get(user=user).ai_summons == 1


@pytest.mark.parametrize("url, target, body", ENDPOINTS)
def test_no_summons_means_no_ai_call_at_all(user, url, target, body):
    _set(user, ai_summons=0)
    with patch(target, return_value=("answer", True)) as ai:
        response = _api(user).post(url, body, format="json")
    assert response.status_code == 402
    ai.assert_not_called()


@pytest.mark.parametrize("url, target, body", ENDPOINTS)
def test_the_last_summon_is_reserved_before_the_ai_is_called(user, url, target, body):
    """A second request that arrives while the first waits for the AI is refused."""
    _set(user, ai_summons=1)
    seen = {}

    def slow_ai(*args, **kwargs):
        # the summon is already gone while the answer is being fetched
        seen["during"] = Profile.objects.get(user=user).ai_summons
        seen["second"] = _api(user).post(url, body, format="json").status_code
        return "answer", True

    with patch(target, side_effect=slow_ai):
        first = _api(user).post(url, body, format="json")
    assert first.status_code == 200
    assert seen == {"during": 0, "second": 402}
