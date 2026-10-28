import pytest
from django.test import Client
from django.utils import timezone

from game.models import Enrollment, Location, Mission, MissionTask, Track
from users.models import User

PW = "x-Test-pass-1"


@pytest.fixture
def su(db):
    return User.objects.create_superuser(username="adm", email="a@e.com", password=PW)


@pytest.fixture
def client(su):
    c = Client()
    assert c.login(username="adm", password=PW)
    return c


def get(c, url):
    return c.get(url, secure=True)


def post(c, url, data):
    return c.post(url, data, secure=True, follow=True)


def test_index_cards(client):
    r = get(client, "/admin/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Учеников" in body and "Выдать роль преподавателя" in body


def test_user_pages(client, su):
    assert get(client, "/admin/users/user/?is_teacher__exact=0&is_active__exact=1").status_code == 200
    r = get(client, f"/admin/users/user/{su.pk}/change/")
    assert r.status_code == 200 and "is_teacher" in r.content.decode()


def test_user_actions(client, su):
    u = User.objects.create_user(username="stu", email="s@e.com", password=PW)
    other = User.objects.create_superuser(username="su2", email="b@e.com", password=PW)
    url = "/admin/users/user/"
    post(client, url, {"action": "make_teacher", "_selected_action": [u.pk]})
    u.refresh_from_db()
    assert u.is_teacher
    post(client, url, {"action": "remove_teacher", "_selected_action": [u.pk]})
    u.refresh_from_db()
    assert not u.is_teacher
    post(client, url, {"action": "block_users", "_selected_action": [u.pk, other.pk, su.pk]})
    u.refresh_from_db()
    other.refresh_from_db()
    su.refresh_from_db()
    assert not u.is_active and other.is_active and su.is_active
    post(client, url, {"action": "unblock_users", "_selected_action": [u.pk]})
    u.refresh_from_db()
    assert u.is_active


def test_mission_publish_action(client):
    loc = Location.objects.create(title="W", order=1)
    empty = Mission.objects.create(location=loc, title="E", order=1, is_active=False)
    full = Mission.objects.create(location=loc, title="F", order=2, is_active=False)
    MissionTask.objects.create(mission=full, task_type="story", title_ru="t", order=1)
    post(client, "/admin/game/mission/", {"action": "publish_missions", "_selected_action": [empty.pk, full.pk]})
    empty.refresh_from_db()
    full.refresh_from_db()
    assert not empty.is_active and full.is_active
    post(client, "/admin/game/mission/", {"action": "unpublish_missions", "_selected_action": [full.pk]})
    full.refresh_from_db()
    assert not full.is_active


def test_track_admin_and_enrollment(client, su):
    t = Track.objects.create(slug="c1", title="C", owner=su, join_code="ABC123")
    stu = User.objects.create_user(username="stu", email="s@e.com", password=PW)
    Enrollment.objects.create(user=stu, track=t, consented_at=timezone.now())
    assert get(client, "/admin/game/track/?q=ABC123&owner__is_teacher__exact=0").status_code == 200
    change_html = get(client, f"/admin/game/track/{t.pk}/change/").content.decode()
    assert 'name="owner"' in change_html and 'name="is_public"' in change_html
    assert get(client, "/admin/game/enrollment/").status_code == 200
    User.objects.create_user(username="st", email="st@e.com", password=PW, is_staff=True)
    c2 = Client()
    c2.login(username="st", password=PW)
    assert get(c2, "/admin/game/enrollment/").status_code in (302, 403)


def test_login_without_next_redirects_to_admin(su):
    c = Client()
    r = c.post("/admin/login/", {"username": "adm", "password": PW, "next": "/admin/"}, secure=True)
    assert r.status_code == 302 and r.url == "/admin/"
    from django.conf import settings

    assert settings.LOGIN_REDIRECT_URL == "/admin/"


def test_token_blacklist_hidden_in_index(client):
    body = get(client, "/admin/").content.decode()
    assert "token_blacklist" not in body.lower()
    assert "Курсы" in body
