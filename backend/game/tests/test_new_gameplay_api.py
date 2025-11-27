import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from game.models import LeaderboardEntry, Location, Mission, MissionTask, Rank, Track
from users.models import User


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.fixture()
def user(db):
    u = User.objects.create_user(username="storyteller", password="pass1234")
    return u


@pytest.fixture()
def gameplay_content(db):
    track = Track.objects.create(slug="python", title="Python Path", order=1)
    loc = Location.objects.create(track=track, title="World", order=1)
    mission = Mission.objects.create(location=loc, title="Mission", order=1)
    MissionTask.objects.create(
        mission=mission,
        order=1,
        task_type="story",
        title_ru="История",
        body_ru="Сюжет",
        xp_reward=5,
    )
    MissionTask.objects.create(
        mission=mission,
        order=2,
        task_type="quiz",
        title_ru="Викторина",
        xp_reward=10,
        data={"questions": [{"q": "2+2?", "options": ["4", "5"], "answer": "4"}]},
    )
    Rank.objects.create(
        slug="novice",
        title_ru="Новичок",
        title_en="Novice",
        min_level=1,
        min_xp=0,
        order=1,
    )
    return track, mission


def test_mission_tasks_endpoint_returns_steps(api_client, gameplay_content):
    _, mission = gameplay_content
    resp = api_client.get(reverse("missiontask-list"), {"mission": mission.id})
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 2
    assert payload[0]["task_type"] == "story"
    assert payload[1]["task_type"] == "quiz"


def test_task_progress_crud_requires_auth(api_client, gameplay_content, user):
    _, mission = gameplay_content
    task = mission.tasks.first()
    create_url = reverse("task-progress-list")
    # unauthenticated -> 401
    r_unauth = api_client.post(create_url, {"task": task.id, "status": "in_progress"})
    assert r_unauth.status_code == 401

    api_client.force_authenticate(user=user)
    r = api_client.post(create_url, {"task": task.id, "status": "in_progress"}, format="json")
    assert r.status_code == 201
    entry_id = r.json()["id"]

    patch = api_client.patch(
        reverse("task-progress-detail", args=[entry_id]),
        {"status": "completed", "best_score": 100},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "completed"


def test_rank_and_leaderboard_endpoints(api_client, gameplay_content, user):
    track, _ = gameplay_content
    profile = user.profile
    profile.xp = 250
    profile.save()
    LeaderboardEntry.objects.create(
        track=track,
        user=user,
        scope="track",
        period_label="all_time",
        xp_total=profile.xp,
        position=1,
    )

    ranks = api_client.get(reverse("rank-list"))
    assert ranks.status_code == 200
    assert ranks.json()[0]["slug"] == "novice"

    leaderboard = api_client.get(reverse("leaderboard-list"), {"track": track.slug})
    assert leaderboard.status_code == 200
    payload = leaderboard.json()
    assert len(payload) == 1
    assert payload[0]["user_display"]["username"] == user.username