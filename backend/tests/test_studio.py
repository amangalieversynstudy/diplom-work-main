"""Tests for the Teacher Studio API (owner-scoped course authoring).

Covers three guarantees that can break independently:
1. Ownership scoping — a teacher only sees/edits their own Track→Location→
   Mission tree; another teacher's content is invisible (404) and cannot be
   written into (403).
2. Public lockdown — the public content API (/api/tracks etc.) is read-only for
   everyone except superusers, so teachers cannot bypass scoping through it.
3. Cabinet scoping — the teacher cabinet shows only students doing *this*
   teacher's courses; superusers still see everyone.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.models import Location, Mission, Progress, Track

User = get_user_model()

TRACKS = "/api/teacher/studio/tracks/"
LOCATIONS = "/api/teacher/studio/locations/"
MISSIONS = "/api/teacher/studio/missions/"


# ── fixtures / helpers ───────────────────────────────────────────────────────


def _teacher(username):
    return User.objects.create_user(
        username=username, password="TestPass123!", is_staff=True
    )


def _superuser(username="root"):
    return User.objects.create_user(
        username=username, password="TestPass123!", is_staff=True, is_superuser=True
    )


def _student(username):
    return User.objects.create_user(username=username, password="TestPass123!")


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _track(owner, title="Course"):
    return Track.objects.create(
        slug=f"{title.lower()}-{owner.username}",
        title=title,
        title_ru=title,
        owner=owner,
    )


def _location(track, title="Section"):
    return Location.objects.create(track=track, title=title, title_ru=title)


def _mission(location, title="Mission"):
    return Mission.objects.create(location=location, title=title, title_ru=title)


# ── permissions ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_anonymous_cannot_access_studio():
    assert APIClient().get(TRACKS).status_code in (401, 403)


@pytest.mark.django_db
def test_non_staff_student_forbidden():
    assert _client(_student("stu")).get(TRACKS).status_code == 403


# ── track CRUD + ownership ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_teacher_creates_track_sets_owner_and_slug():
    t = _teacher("t1")
    resp = _client(t).post(TRACKS, {"title_ru": "Питон с нуля"}, format="json")
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["slug"]  # auto-generated
    track = Track.objects.get(id=body["id"])
    assert track.owner_id == t.id
    assert track.title == "Питон с нуля"  # legacy mirror populated
    assert track.is_active is False  # new courses start as drafts


@pytest.mark.django_db
def test_track_requires_a_title():
    resp = _client(_teacher("t1")).post(TRACKS, {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_duplicate_titles_get_unique_slugs():
    t = _teacher("t1")
    a = _client(t).post(TRACKS, {"title_en": "Algo"}, format="json").json()
    b = _client(t).post(TRACKS, {"title_en": "Algo"}, format="json").json()
    assert a["slug"] != b["slug"]


@pytest.mark.django_db
def test_teacher_lists_only_own_tracks():
    t1, t2 = _teacher("t1"), _teacher("t2")
    _track(t1, "Mine")
    _track(t2, "Theirs")
    body = _client(t1).get(TRACKS).json()
    titles = {row["title_ru"] for row in body}
    assert titles == {"Mine"}


@pytest.mark.django_db
def test_teacher_cannot_touch_others_track():
    t1, t2 = _teacher("t1"), _teacher("t2")
    other = _track(t2, "Theirs")
    c = _client(t1)
    assert c.get(f"{TRACKS}{other.id}/").status_code == 404
    assert c.patch(f"{TRACKS}{other.id}/", {"title_ru": "Hax"}, format="json").status_code == 404
    assert c.delete(f"{TRACKS}{other.id}/").status_code == 404


@pytest.mark.django_db
def test_superuser_sees_all_tracks():
    # The DB may carry a seeded system track, so assert the two teachers' tracks
    # are both visible to the superuser (a single teacher would see only one).
    _track(_teacher("t1"), "A")
    _track(_teacher("t2"), "B")
    titles = {row["title_ru"] for row in _client(_superuser()).get(TRACKS).json()}
    assert {"A", "B"} <= titles


# ── location / mission ownership ─────────────────────────────────────────────


@pytest.mark.django_db
def test_location_created_under_own_track():
    t = _teacher("t1")
    track = _track(t, "Mine")
    resp = _client(t).post(
        LOCATIONS, {"track": track.id, "title_ru": "Раздел 1"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert Location.objects.get(id=resp.json()["id"]).track_id == track.id


@pytest.mark.django_db
def test_location_rejected_under_foreign_track():
    t1, t2 = _teacher("t1"), _teacher("t2")
    foreign = _track(t2, "Theirs")
    resp = _client(t1).post(
        LOCATIONS, {"track": foreign.id, "title_ru": "X"}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_locations_filtered_by_track_param():
    t = _teacher("t1")
    a, b = _track(t, "A"), _track(t, "B")
    _location(a, "a1")
    _location(b, "b1")
    body = _client(t).get(LOCATIONS, {"track": a.id}).json()
    assert {r["title_ru"] for r in body} == {"a1"}


@pytest.mark.django_db
def test_mission_created_under_own_location():
    t = _teacher("t1")
    loc = _location(_track(t, "Mine"))
    resp = _client(t).post(
        MISSIONS,
        {"location": loc.id, "title_ru": "Миссия 1", "xp_reward": 25},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    m = Mission.objects.get(id=resp.json()["id"])
    assert m.location_id == loc.id and m.xp_reward == 25


@pytest.mark.django_db
def test_mission_rejected_under_foreign_location():
    t1, t2 = _teacher("t1"), _teacher("t2")
    foreign_loc = _location(_track(t2, "Theirs"))
    resp = _client(t1).post(
        MISSIONS, {"location": foreign_loc.id, "title_ru": "X"}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_teacher_cannot_list_foreign_missions():
    t1, t2 = _teacher("t1"), _teacher("t2")
    _mission(_location(_track(t2, "Theirs")))
    assert _client(t1).get(MISSIONS).json() == []


# ── public content API lockdown ──────────────────────────────────────────────


@pytest.mark.django_db
def test_public_track_read_is_open():
    _track(_teacher("t1"), "Public")
    assert APIClient().get("/api/tracks/").status_code == 200


@pytest.mark.django_db
def test_public_track_write_forbidden_for_teacher():
    t = _teacher("t1")
    track = _track(t, "Mine")
    # Even the owner cannot write via the public endpoint — must use Studio.
    resp = _client(t).patch(f"/api/tracks/{track.id}/", {"order": 9}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_public_track_write_allowed_for_superuser():
    track = _track(_teacher("t1"), "Mine")
    resp = _client(_superuser()).patch(
        f"/api/tracks/{track.id}/", {"order": 9}, format="json"
    )
    assert resp.status_code == 200
    track.refresh_from_db()
    assert track.order == 9


# ── cabinet scoping ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_cabinet_scoped_to_own_students():
    t1, t2 = _teacher("t1"), _teacher("t2")
    m1 = _mission(_location(_track(t1, "A")), "m1")
    m2 = _mission(_location(_track(t2, "B")), "m2")
    sx, sy = _student("sx"), _student("sy")
    Progress.objects.create(user=sx, mission=m1, status="in_progress")
    Progress.objects.create(user=sy, mission=m2, status="in_progress")

    body1 = _client(t1).get("/api/teacher/students/").json()
    assert {s["username"] for s in body1["students"]} == {"sx"}

    body2 = _client(t2).get("/api/teacher/students/").json()
    assert {s["username"] for s in body2["students"]} == {"sy"}


@pytest.mark.django_db
def test_cabinet_superuser_sees_all_students():
    t1 = _teacher("t1")
    m1 = _mission(_location(_track(t1, "A")), "m1")
    sx, sy = _student("sx"), _student("sy")
    Progress.objects.create(user=sx, mission=m1, status="in_progress")
    Progress.objects.create(user=sy, mission=m1, status="in_progress")

    body = _client(_superuser()).get("/api/teacher/students/").json()
    assert {s["username"] for s in body["students"]} == {"sx", "sy"}
