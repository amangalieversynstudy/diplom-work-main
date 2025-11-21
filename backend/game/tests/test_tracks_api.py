import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from game.models import Location, Mission, Track


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_track_list_returns_worlds_and_missions(api_client):
    track = Track.objects.create(slug="python", title="Python", order=1)
    world = Location.objects.create(track=track, title="World", order=1)
    Mission.objects.create(location=world, title="Intro", order=1)

    resp = api_client.get(reverse("track-list"))
    assert resp.status_code == 200
    payload = resp.json()
    target = next((item for item in payload if item["slug"] == "python"), None)
    assert target is not None
    assert target["worlds"][0]["title"] == "World"
    assert target["worlds"][0]["missions"][0]["title"] == "Intro"