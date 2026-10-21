"""Draft missions stay hidden from learners; locked_reason explains why a mission is locked."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import Enrollment, Location, Mission, MissionTask, Progress, Track

User = get_user_model()


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _setup():
    teacher = User.objects.create_user(username="draft_teacher", password="DraftPass123!", is_teacher=True)
    learner = User.objects.create_user(username="draft_learner", password="DraftPass123!")
    track = Track.objects.create(slug="draft-course", title="Draft course", owner=teacher, is_public=False)
    Enrollment.objects.create(user=learner, track=track, consented_at=timezone.now())
    location = Location.objects.create(track=track, title="L")
    draft = Mission.objects.create(location=location, title="Draft", is_active=False)
    MissionTask.objects.create(mission=draft, order=1, task_type="story", title="Secret", body="secret body")
    live = Mission.objects.create(location=location, title="Live", order=2)
    return teacher, learner, track, location, draft, live


@pytest.mark.django_db
def test_learner_gets_404_for_a_draft_and_does_not_see_it_in_lists():
    teacher, learner, track, location, draft, live = _setup()
    client = _client(learner)
    assert client.get(f"/api/missions/{draft.pk}/").status_code == 404
    assert client.get(f"/api/missions/{live.pk}/").status_code == 200
    ids = {m["id"] for m in client.get(f"/api/tracks/{track.pk}/").json()["worlds"][0]["missions"]}
    assert ids == {live.pk}
    listed = client.get("/api/missions/").json()
    listed = listed["results"] if isinstance(listed, dict) else listed
    assert {m["id"] for m in listed} == {live.pk}
    assert "Secret" not in client.get("/api/mission-tasks/").content.decode()


@pytest.mark.django_db
def test_owner_still_sees_the_draft():
    teacher, learner, track, location, draft, live = _setup()
    client = _client(teacher)
    response = client.get(f"/api/missions/{draft.pk}/")
    assert response.status_code == 200
    assert response.json()["locked_reason"] == "draft"
    ids = {m["id"] for m in client.get(f"/api/tracks/{track.pk}/").json()["worlds"][0]["missions"]}
    assert ids == {draft.pk, live.pk}


@pytest.mark.django_db
def test_locked_reason_level_and_prerequisites():
    teacher, learner, track, location, draft, live = _setup()
    gated = Mission.objects.create(location=location, title="Gated", order=3, min_level=5)
    chained = Mission.objects.create(location=location, title="Chained", order=4)
    chained.prerequisites.add(live)
    client = _client(learner)
    body = client.get(f"/api/missions/{gated.pk}/").json()
    assert (body["locked_reason"], body["available"]) == ("level", False)
    body = client.get(f"/api/missions/{chained.pk}/").json()
    assert (body["locked_reason"], body["available"]) == ("prerequisites", False)
    body = client.get(f"/api/missions/{live.pk}/").json()
    assert (body["locked_reason"], body["available"]) == (None, True)
    Progress.objects.create(user=learner, mission=live, completed=True)
    assert client.get(f"/api/missions/{chained.pk}/").json()["locked_reason"] is None
