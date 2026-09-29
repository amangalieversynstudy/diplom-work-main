"""A teacher opens one student's learning picture from the warning list."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.models import Location, Mission, MissionTask, Progress, TaskProgress, Track

User = get_user_model()

pytestmark = pytest.mark.django_db


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _teacher(name):
    return User.objects.create_user(name, f"{name}@example.com", "S3cure-pass-1", is_staff=True)


def _course(owner, slug):
    track = Track.objects.create(slug=slug, title=slug.title(), is_active=True, owner=owner)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title=f"{slug} mission", order=1)
    step = MissionTask.objects.create(mission=mission, order=1, task_type="code", title=f"{slug} step")
    return mission, step


@pytest.fixture
def world():
    teacher = _teacher("teacher")
    other_teacher = _teacher("other")
    mine, my_step = _course(teacher, "mine")
    theirs, their_step = _course(other_teacher, "theirs")
    student = User.objects.create_user("student", "s@example.com", "S3cure-pass-1")
    Progress.objects.create(user=student, mission=mine, status="in_progress")
    TaskProgress.objects.create(user=student, task=my_step, status="in_progress", attempts=4)
    Progress.objects.create(user=student, mission=theirs, status="in_progress")
    TaskProgress.objects.create(user=student, task=their_step, status="in_progress", attempts=2)
    return {"teacher": teacher, "other": other_teacher, "student": student, "mine": mine, "theirs": theirs}


def _url(student):
    return f"/api/teacher/students/{student.pk}/learning/"


def test_a_teacher_sees_their_students_picture(world):
    response = _api(world["teacher"]).get(_url(world["student"]))
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["student"]["username"] == "student"
    assert data["status"] == "stuck"
    assert [item["title"] for item in data["stuck"]] == ["mine step"]


def test_the_picture_only_covers_the_teachers_own_courses(world):
    data = _api(world["teacher"]).get(_url(world["student"])).json()
    assert [m["id"] for m in data["missions"]] == [world["mine"].pk]
    assert data["summary"]["missions_total"] == 1
    assert "theirs" not in str(data)


def test_another_teachers_view_of_the_same_student_is_scoped_too(world):
    data = _api(world["other"]).get(_url(world["student"])).json()
    assert [m["id"] for m in data["missions"]] == [world["theirs"].pk]


def test_a_student_of_nobody_is_a_404(world):
    stranger = User.objects.create_user("stranger", "x@example.com", "S3cure-pass-1")
    assert _api(world["teacher"]).get(_url(stranger)).status_code == 404


def test_a_superuser_sees_everyone_across_courses(world):
    admin = User.objects.create_superuser("admin", "a@example.com", "S3cure-pass-1")
    data = _api(admin).get(_url(world["student"])).json()
    assert len(data["missions"]) == 2


def test_students_cannot_open_the_teacher_view(world):
    assert _api(world["student"]).get(_url(world["student"])).status_code == 403


def test_anonymous_is_refused(world):
    assert APIClient().get(_url(world["student"])).status_code in (401, 403)


def test_a_staff_account_is_not_a_student(world):
    assert _api(world["teacher"]).get(_url(world["other"])).status_code == 404
