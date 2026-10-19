"""Studio limits that protect learners' data and the platform (superusers are exempt)."""

from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import Enrollment, Mission, MissionTask, TaskProgress, Track

User = get_user_model()
TRACKS = "/api/teacher/studio/tracks/"
LOCATIONS = "/api/teacher/studio/locations/"
MISSIONS = "/api/teacher/studio/missions/"
TASKS = "/api/teacher/studio/tasks/"


def _user(name, **extra):
    return User.objects.create_user(username=name, password="StudioPass123!", **extra)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _course(api, title="Курс"):
    track = api.post(TRACKS, {"title_ru": title}, format="json").json()
    location = api.post(LOCATIONS, {"track": track["id"], "title_ru": "Раздел"}, format="json").json()
    mission = api.post(
        MISSIONS, {"location": location["id"], "title_ru": "Миссия", "xp_reward": 10}, format="json"
    ).json()
    return track, location, mission


@pytest.mark.django_db
def test_course_quota_for_teachers_not_for_superusers(settings):
    settings.STUDIO_LIMITS = {**settings.STUDIO_LIMITS, "tracks_per_teacher": 2, "tracks_per_vetted_teacher": 3}
    cases = (
        (_user("q1", is_teacher=True), 2, 400),
        (_user("q2", is_staff=True), 3, 400),
        (_user("q3", is_staff=True, is_superuser=True), 3, 201),
    )
    for user, allowed, last in cases:
        api = _client(user)
        codes = [api.post(TRACKS, {"title_ru": f"К{i}"}, format="json").status_code for i in range(allowed + 1)]
        assert codes == [201] * allowed + [last], (user.username, codes)


@pytest.mark.django_db
def test_mission_and_step_quotas(settings):
    settings.STUDIO_LIMITS = {**settings.STUDIO_LIMITS, "missions_per_track": 1, "tasks_per_mission": 1}
    api = _client(_user("q4", is_teacher=True))
    _, location, mission = _course(api)
    assert api.post(MISSIONS, {"location": location["id"], "title_ru": "Ещё"}, format="json").status_code == 400
    step = {"mission": mission["id"], "task_type": "story", "order": 1, "title_ru": "Шаг", "body_ru": "Текст"}
    assert api.post(TASKS, step, format="json").status_code == 201
    assert api.post(TASKS, {**step, "order": 2}, format="json").status_code == 400


@pytest.mark.django_db
def test_nothing_with_learners_work_can_be_deleted():
    teacher = _user("d1", is_teacher=True)
    api = _client(teacher)
    track, location, mission = _course(api)
    step = api.post(
        TASKS, {"mission": mission["id"], "task_type": "story", "order": 1, "title_ru": "Шаг", "body_ru": "Т"}, format="json"
    ).json()
    learner = _user("d_learner")
    TaskProgress.objects.create(user=learner, task_id=step["id"], attempts=1, status="in_progress")

    for url in (
        f"{TASKS}{step['id']}/",
        f"{MISSIONS}{mission['id']}/",
        f"{LOCATIONS}{location['id']}/",
        f"{TRACKS}{track['id']}/",
    ):
        assert api.delete(url).status_code == 400, url
    assert MissionTask.objects.filter(pk=step["id"]).exists()

    # the teacher's own trial run does not lock the course; then it can go
    TaskProgress.objects.filter(user=learner).delete()
    TaskProgress.objects.create(user=teacher, task_id=step["id"], attempts=1, status="completed")
    assert api.delete(f"{TRACKS}{track['id']}/").status_code == 204


@pytest.mark.django_db
def test_a_class_with_learners_cannot_be_deleted_but_a_superuser_still_can():
    teacher = _user("d2", is_teacher=True)
    track, _, _ = _course(_client(teacher))
    Enrollment.objects.create(user=_user("d2_l"), track_id=track["id"], consented_at=timezone.now())
    assert _client(teacher).delete(f"{TRACKS}{track['id']}/").status_code == 400
    root = _user("d2_root", is_staff=True, is_superuser=True)
    assert _client(root).delete(f"{TRACKS}{track['id']}/").status_code == 204


@pytest.mark.django_db
def test_content_cannot_move_to_another_parent():
    api = _client(_user("m1", is_teacher=True))
    _, location_a, mission = _course(api, "А")
    _, location_b, _ = _course(api, "Б")
    moved = api.patch(f"{MISSIONS}{mission['id']}/", {"location": location_b["id"]}, format="json")
    assert moved.status_code == 400
    assert Mission.objects.get(pk=mission["id"]).location_id == location_a["id"]


@pytest.mark.django_db
def test_min_level_is_not_set_from_the_studio():
    api = _client(_user("m2", is_teacher=True))
    _, _, mission = _course(api)
    api.patch(f"{MISSIONS}{mission['id']}/", {"min_level": 5}, format="json")
    assert Mission.objects.get(pk=mission["id"]).min_level == 1


@pytest.mark.django_db
def test_bad_filters_are_an_empty_list_not_a_server_error():
    api = _client(_user("m3", is_teacher=True))
    assert api.get(LOCATIONS, {"track": "abc"}).status_code == 200
    assert api.get(MISSIONS, {"location": "abc"}).status_code == 200


@pytest.mark.django_db
def test_slugs_stay_unique_for_cyrillic_titles():
    api = _client(_user("m4", is_staff=True))
    slugs = {api.post(TRACKS, {"title_ru": "Курс"}, format="json").json()["slug"] for _ in range(5)}
    assert len(slugs) == 5


@pytest.mark.django_db
def test_descriptions_are_capped():
    api = _client(_user("m5", is_teacher=True))
    assert api.post(TRACKS, {"title_ru": "К", "description_ru": "x" * 5001}, format="json").status_code == 400


@pytest.mark.django_db
def test_a_public_course_has_no_class_code_and_cannot_be_joined():
    staff = _user("p1", is_staff=True)
    track = Track.objects.create(slug="pub-p1", title="P", owner=staff, is_public=True, join_code="PUBLIC23")
    assert _client(staff).post(f"{TRACKS}{track.pk}/new-code/").status_code == 400
    learner = _client(_user("p1_l"))
    assert learner.get("/api/classes/lookup/", {"code": "PUBLIC23"}).status_code == 404
    joined = learner.post("/api/classes/join/", {"code": "PUBLIC23", "consent": True}, format="json")
    assert joined.status_code == 404


@pytest.mark.django_db
def test_set_course_owner_refuses_unsafe_moves():
    Track.objects.create(slug="pub-owner", title="P")
    _user("o1", is_teacher=True)
    with pytest.raises(CommandError):
        call_command("set_course_owner", "pub-owner", "o1")
    staff, other = _user("o2", is_staff=True), _user("o3", is_staff=True)
    call_command("set_course_owner", "pub-owner", "o2")
    klass = Track.objects.create(slug="cls-owner", title="C", owner=staff, is_public=False, join_code="CLASS234")
    Enrollment.objects.create(user=_user("o_l"), track=klass, consented_at=timezone.now())
    with pytest.raises(CommandError):
        call_command("set_course_owner", "cls-owner", "o3")
    call_command("set_course_owner", "cls-owner", "o3", "--transfer-class")
    assert Track.objects.get(slug="cls-owner").owner == other


@pytest.mark.django_db
def test_the_migration_closes_public_courses_of_unvetted_owners():
    migration = import_module("game.migrations.0021_close_unvetted_public_tracks")
    unvetted = Track.objects.create(slug="mig-u", title="U", owner=_user("mig_t", is_teacher=True))
    vetted = Track.objects.create(slug="mig-v", title="V", owner=_user("mig_s", is_staff=True))
    migration.close_unvetted_public_tracks(apps, None)
    unvetted.refresh_from_db()
    vetted.refresh_from_db()
    assert unvetted.is_public is False and len(unvetted.join_code) == 8
    assert vetted.is_public is True
