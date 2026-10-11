import pytest
from django.test import Client
from game.models import Location, Mission
from users.models import User


@pytest.mark.django_db
def test_admin_pages_render():
    User.objects.create_superuser(
        username="adm", email="adm@example.com", password="x-Test-pass-1"
    )
    loc = Location.objects.create(title="World 1", order=1)
    mission = Mission.objects.create(location=loc, title="Intro", order=1)
    client = Client()
    assert client.login(username="adm", password="x-Test-pass-1")
    for url in (
        "/admin/",
        "/admin/game/mission/",
        f"/admin/game/mission/{mission.pk}/change/",
    ):
        resp = client.get(url, secure=True)
        assert resp.status_code == 200, url
