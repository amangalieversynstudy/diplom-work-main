"""The self-service teacher role: chosen at sign-up, limited to the teacher's own courses.

``is_teacher`` opens the cabinet, analytics and Studio like ``is_staff`` does, but it never opens the
Django admin and it never makes the account count as a learner in the metrics.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from game.metrics import compute_metrics
from game.models import Enrollment, Location, Mission, MissionTask, Progress, TaskProgress, Track

User = get_user_model()

REGISTER_URL = "/api/auth/register/"


@pytest.fixture(autouse=True)
def _fresh_ratelimit():
    cache.clear()
    yield
    cache.clear()


def _signup(role=None, name="role_user", **extra):
    body = {"username": name, "password": "RolePass123!", **extra}
    if role is not None:
        body["role"] = role
    return APIClient().post(REGISTER_URL, body)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _course(owner, slug):
    track = Track.objects.create(slug=slug, title=slug, owner=owner)
    location = Location.objects.create(track=track, title="Loc")
    mission = Mission.objects.create(location=location, title="Mission", xp_reward=10)
    task = MissionTask.objects.create(mission=mission, order=1, task_type="quiz")
    return track, mission, task


@pytest.mark.django_db
def test_default_signup_is_a_student():
    assert _signup().status_code == 201
    user = User.objects.get(username="role_user")
    assert (user.is_teacher, user.is_staff, user.can_teach) == (False, False, False)


@pytest.mark.django_db
def test_teacher_role_needs_no_code_and_is_not_staff():
    assert _signup("teacher").status_code == 201
    user = User.objects.get(username="role_user")
    assert user.is_teacher is True
    assert user.is_staff is False  # no way into the Django admin
    assert user.can_teach is True


@pytest.mark.django_db
def test_an_unknown_role_is_rejected():
    assert _signup("admin").status_code == 400
    assert not User.objects.filter(username="role_user").exists()


@pytest.mark.django_db
@override_settings(TEACHER_SELF_REGISTRATION=False, TEACHER_INVITE_CODE="")
def test_teacher_role_can_be_switched_off():
    resp = _signup("teacher")
    assert resp.status_code == 400
    assert "teacher_code" in resp.json()  # the form shows the error at the code field
    assert not User.objects.filter(username="role_user").exists()
    # students are not affected
    assert _signup("student", name="still_ok").status_code == 201


@pytest.mark.django_db
def test_student_cannot_open_teacher_endpoints():
    _signup("student")
    student = User.objects.get(username="role_user")
    for url in ("/api/teacher/students/", "/api/analytics/metrics/", "/api/analytics/early-warning/"):
        assert _client(student).get(url).status_code == 403


@pytest.mark.django_db
def test_teacher_role_opens_cabinet_and_analytics():
    _signup("teacher")
    teacher = User.objects.get(username="role_user")
    for url in ("/api/teacher/students/", "/api/analytics/metrics/", "/api/analytics/early-warning/"):
        assert _client(teacher).get(url).status_code == 200


@pytest.mark.django_db
def test_me_reports_the_teaching_flag():
    _signup("teacher")
    teacher = User.objects.get(username="role_user")
    body = _client(teacher).get("/api/profile/me/").json()
    assert body["can_teach"] is True and body["is_teacher"] is True and body["is_staff"] is False


@pytest.mark.django_db
def test_a_teacher_sees_only_learners_of_their_own_courses():
    _signup("teacher", name="teacher_a")
    teacher_a = User.objects.get(username="teacher_a")
    teacher_b = User.objects.create_user(username="teacher_b", password="x", is_teacher=True)
    track_a, mission_a, task_a = _course(teacher_a, "course-a")
    track_b, mission_b, task_b = _course(teacher_b, "course-b")
    mine = User.objects.create_user(username="learner_of_a", password="x")
    theirs = User.objects.create_user(username="learner_of_b", password="x")
    now = timezone.now()
    # a self-service teacher sees learners who joined their class (consent), not everyone who touched a course
    for learner, track in ((mine, track_a), (theirs, track_b)):
        Enrollment.objects.create(user=learner, track=track, consented_at=now)
    for learner, mission, task in ((mine, mission_a, task_a), (theirs, mission_b, task_b)):
        Progress.objects.create(
            user=learner, mission=mission, status="in_progress", started_at=now, last_started_at=now
        )
        TaskProgress.objects.create(
            user=learner, task=task, attempts=1, status="in_progress", last_submitted_at=now
        )

    names = [row["username"] for row in _client(teacher_a).get("/api/teacher/students/").json()["students"]]

    assert names == ["learner_of_a"]


@pytest.mark.django_db
def test_a_teacher_never_counts_as_a_learner():
    teacher = User.objects.create_user(username="teach_x", password="x", is_teacher=True)
    _, mission, task = _course(teacher, "course-x")
    now = timezone.now()
    # a teacher trying their own course must not show up as a student in their own cabinet or metrics
    Progress.objects.create(
        user=teacher, mission=mission, status="in_progress", started_at=now, last_started_at=now
    )
    TaskProgress.objects.create(
        user=teacher, task=task, attempts=4, status="in_progress", last_submitted_at=now - timedelta(hours=1)
    )

    assert _client(teacher).get("/api/teacher/students/").json()["students"] == []
    assert compute_metrics(teacher)["meta"]["learners"] == 0
    assert _client(teacher).get("/api/analytics/early-warning/").json()["students"] == []


@pytest.mark.django_db
def test_a_teacher_cannot_edit_another_teachers_course_in_the_studio():
    teacher_a = User.objects.create_user(username="studio_a", password="x", is_teacher=True)
    teacher_b = User.objects.create_user(username="studio_b", password="x", is_teacher=True)
    track_b, _, _ = _course(teacher_b, "studio-b")

    resp = _client(teacher_a).patch(f"/api/teacher/studio/tracks/{track_b.pk}/", {"title": "hacked"}, format="json")

    assert resp.status_code in (403, 404)
    track_b.refresh_from_db()
    assert track_b.title == "studio-b"


@pytest.mark.django_db
def test_a_self_service_teacher_has_no_admin_access():
    _signup("teacher")
    teacher = User.objects.get(username="role_user")
    client = APIClient()
    client.force_login(teacher)
    assert client.get("/admin/").status_code in (302, 403)
