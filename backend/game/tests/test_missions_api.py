import pytest
from django.urls import reverse
from game.models import Location, Mission, Progress
from rest_framework.test import APIClient
from users.models import User


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.fixture()
def user(db):
    u = User.objects.create_user(username="player", password="pass1234")
    # ensure profile exists
    assert hasattr(u, "profile")
    return u


@pytest.fixture()
def content(db):
    loc = Location.objects.create(title="World 1", order=1)
    m1 = Mission.objects.create(location=loc, title="Intro", order=1, xp_reward=100)
    m2 = Mission.objects.create(
        location=loc,
        title="Gate",
        order=2,
        xp_reward=150,
        min_level=2,
        is_active=True,
    )
    m2.prerequisites.add(m1)
    m3 = Mission.objects.create(
        location=loc,
        title="Repeatable",
        order=3,
        xp_reward=50,
        repeatable=True,
        repeat_xp_rate=20,
    )
    return loc, m1, m2, m3


def auth(client: APIClient, user: User):
    client.force_authenticate(user=user)


def test_mission_availability_requires_prereq_and_level(api_client, user, content):
    _, m1, m2, _ = content
    auth(api_client, user)

    # before completing m1, m2 should be unavailable (prereq not done)
    resp = api_client.get(reverse("mission-list"))
    assert resp.status_code == 200
    missions = {m["title"]: m for m in resp.json()}
    assert missions["Intro"]["available"] is True
    assert missions["Gate"]["available"] is False

    # complete m1 -> get 100 XP -> level becomes 2 (100 xp per level)
    resp = api_client.post(reverse("mission-complete", args=[m1.id]), {})
    assert resp.status_code == 200
    data = resp.json()
    assert data["xp_added"] == 100
    assert data["profile_level"] == 2

    # now prereq satisfied and level ok => m2 available
    resp = api_client.get(reverse("mission-list"))
    missions = {m["title"]: m for m in resp.json()}
    assert missions["Gate"]["available"] is True


def test_start_increments_attempts_and_sets_status(api_client, user, content):
    _, m1, _, _ = content
    auth(api_client, user)
    # start
    r1 = api_client.post(reverse("mission-start", args=[m1.id]), {})
    assert r1.status_code == 200
    p = r1.json()
    assert p["status"] == "in_progress"
    assert p["attempts"] == 1
    # start again increments attempts (still not completed)
    r2 = api_client.post(reverse("mission-start", args=[m1.id]), {})
    assert r2.status_code == 200
    assert r2.json()["attempts"] == 2


def test_complete_awards_xp_first_time_and_handles_repeat(api_client, user, content):
    _, m1, _, m3 = content
    auth(api_client, user)

    # m1 first completion -> +100 xp
    r1 = api_client.post(reverse("mission-complete", args=[m1.id]))
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["xp_added"] == 100
    assert d1["profile_xp"] == 100

    # m1 repeat (not repeatable) -> +0 xp
    r2 = api_client.post(reverse("mission-complete", args=[m1.id]))
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["xp_added"] == 0
    assert d2["profile_xp"] == 100

    # m3 repeatable: first +50, then +10 (20% of 50)
    r3 = api_client.post(reverse("mission-complete", args=[m3.id]))
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["xp_added"] == 50
    r4 = api_client.post(reverse("mission-complete", args=[m3.id]))
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["xp_added"] == 10


def test_progress_view_returns_only_own(api_client, user, content, db):
    other = User.objects.create_user(username="other", password="x")
    loc, m1, *_ = content
    Progress.objects.create(user=other, mission=m1, completed=True)

    auth(api_client, user)
    resp = api_client.get(reverse("progress-list"))
    assert resp.status_code == 200
    # Should be empty since current user has no progress yet
    assert resp.json() == []


def test_start_and_complete_forbidden_without_prereqs_or_level(
    api_client, user, content
):
    _, m1, m2, _ = content
    # m2 требует m1 и level>=2
    api_client.force_authenticate(user=user)
    # старт без prereq/level
    r1 = api_client.post(reverse("mission-start", args=[m2.id]))
    assert r1.status_code in (401, 403, 400, 403)  # ожидаем отказ
    # сначала завершим m1 (даст уровень 2)
    ok = api_client.post(reverse("mission-complete", args=[m1.id]))
    assert ok.status_code == 200
    # теперь старт m2 должен пройти
    r2 = api_client.post(reverse("mission-start", args=[m2.id]))
    assert r2.status_code == 200


def test_repeat_non_repeatable_gives_zero_xp(api_client, user, content):
    _, m1, _, _ = content
    api_client.force_authenticate(user=user)
    r1 = api_client.post(reverse("mission-complete", args=[m1.id]))
    assert r1.status_code == 200
    r2 = api_client.post(reverse("mission-complete", args=[m1.id]))
    assert r2.status_code == 200
    assert r2.json()["xp_added"] == 0
