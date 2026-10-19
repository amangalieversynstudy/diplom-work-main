"""A teacher sees a learner only through the teacher's own courses.

Logins, free practice, other teachers' classes and a class the learner left stay private: the cabinet, the
early-warning list, the metrics, the live feed, the student page and the authorship report all agree. A superuser
(and therefore the pilot report) keeps the platform-wide view.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.metrics import compute_metrics
from game.models import (
    CodeRun,
    Enrollment,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)
from game.warning import assess_students

User = get_user_model()


def _user(name, **extra):
    return User.objects.create_user(username=name, password="ScopePass123!", **extra)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _course(owner, slug, *, public):
    track = Track.objects.create(slug=slug, title=slug, owner=owner, is_public=public)
    location = Location.objects.create(track=track, title="L")
    mission = Mission.objects.create(location=location, title=f"M {slug}", xp_reward=10)
    quiz = MissionTask.objects.create(mission=mission, order=1, task_type="quiz", title="Quiz")
    code = MissionTask.objects.create(mission=mission, order=2, task_type="code", title="Code")
    return track, mission, quiz, code


def _join(learner, track, when=None):
    return Enrollment.objects.create(user=learner, track=track, consented_at=when or timezone.now())


def _roster(teacher):
    return {row["username"]: row for row in _client(teacher).get("/api/teacher/students/").json()["students"]}


@pytest.fixture
def two_teachers():
    """Teacher A (vetted) owns a public course and a class; teacher B (self-service) owns a class."""
    a = _user("teacher_a", is_staff=True)
    b = _user("teacher_b", is_teacher=True)
    public = _course(a, "a-public", public=True)
    a_class = _course(a, "a-class", public=False)
    b_class = _course(b, "b-class", public=False)
    return a, b, public, a_class, b_class


@pytest.mark.django_db
def test_roster_counts_only_the_teachers_own_courses(two_teachers):
    a, b, public, a_class, b_class = two_teachers
    learner = _user("learner")
    _join(learner, b_class[0])
    now = timezone.now()
    Progress.objects.create(user=learner, mission=public[1], completed=True, status="completed",
                            started_at=now, last_started_at=now, completed_at=now, xp_earned=10)
    Progress.objects.create(user=learner, mission=b_class[1], completed=True, status="completed",
                            started_at=now, last_started_at=now, completed_at=now, xp_earned=10)
    learner.profile.xp = 500
    learner.profile.level = 6
    learner.profile.current_streak = 4
    learner.profile.save(update_fields=["xp", "level", "current_streak"])

    row_a = _roster(a)["learner"]
    assert row_a["completed_count"] == 1
    assert row_a["xp"] == 10  # XP of A's courses, not the profile total
    assert row_a["level"] is None and row_a["current_streak"] is None

    row_b = _roster(b)["learner"]
    assert row_b["completed_count"] == 1 and row_b["xp"] == 10

    root = _user("root", is_staff=True, is_superuser=True)
    row_root = _roster(root)["learner"]
    assert row_root["completed_count"] == 2 and row_root["xp"] == 500 and row_root["level"] == 6


@pytest.mark.django_db
def test_last_activity_ignores_logins_free_practice_and_other_classes(two_teachers):
    a, b, public, a_class, b_class = two_teachers
    learner = _user("quiet_here")
    _join(learner, b_class[0])
    old = timezone.now() - timedelta(days=20)
    Progress.objects.create(user=learner, mission=public[1], status="in_progress",
                            started_at=old, last_started_at=old)
    LearningEvent.objects.create(user=learner, event_type=LearningEvent.LOGIN)
    CodeRun.objects.create(user=learner, task=None, outcome="success", duration_ms=1)
    CodeRun.objects.create(user=learner, task=b_class[3], outcome="success", duration_ms=1)

    row = _roster(a)["quiet_here"]
    assert row["last_active"].startswith(old.date().isoformat())
    warning = {s["username"]: s for s in assess_students(a).values()}["quiet_here"]
    assert warning["days_inactive"] >= 19
    assert {r["code"] for r in warning["reasons"]} == {"inactive"}

    root = _user("root2", is_staff=True, is_superuser=True)
    assert _roster(root)["quiet_here"]["last_active"] >= timezone.now().date().isoformat()


@pytest.mark.django_db
def test_open_work_in_another_teachers_class_does_not_flag_the_learner(two_teachers):
    a, b, public, a_class, b_class = two_teachers
    learner = _user("elsewhere")
    _join(learner, b_class[0])
    old = timezone.now() - timedelta(days=30)
    Progress.objects.create(user=learner, mission=public[1], completed=True, status="completed",
                            started_at=old, last_started_at=old, completed_at=old)
    Progress.objects.create(user=learner, mission=b_class[1], status="in_progress",
                            started_at=old, last_started_at=old)

    assert assess_students(a)[learner.pk]["level"] == "ok"
    assert assess_students(b)[learner.pk]["level"] != "ok"


@pytest.mark.django_db
def test_a_learner_who_left_a_class_disappears_from_its_data_everywhere(two_teachers):
    a, b, public, a_class, b_class = two_teachers
    learner = _user("leaver")
    enrollment = _join(learner, a_class[0])
    now = timezone.now()
    # visible to A through the public course too
    Progress.objects.create(user=learner, mission=public[1], status="in_progress", started_at=now, last_started_at=now)
    Progress.objects.create(user=learner, mission=a_class[1], status="in_progress", started_at=now, last_started_at=now)
    TaskProgress.objects.create(user=learner, task=a_class[2], attempts=4, status="in_progress", last_submitted_at=now)
    CodeRun.objects.create(user=learner, task=a_class[3], outcome="success", passed=True, duration_ms=1)
    LearningEvent.objects.create(user=learner, event_type=LearningEvent.TASK_OPENED, task=a_class[2])

    def class_rows():
        metrics = compute_metrics(a, track_id=a_class[0].pk)
        steps = {row["task_id"]: row["opened"] for row in metrics["tasks"]}
        stuck = [r for r in assess_students(a)[learner.pk]["reasons"] if r["code"] == "stuck_task"]
        feed = _client(a).get("/api/teacher/live/").json()["events"]
        return steps[a_class[2].pk], stuck, len(feed)

    opened, stuck, feed = class_rows()
    assert opened == 1 and stuck and feed >= 1

    enrollment.delete()
    opened, stuck, feed = class_rows()
    assert opened == 0
    assert stuck == []
    assert feed == 0
    assert learner.pk in {s.pk for s in __import__("game.classes", fromlist=["x"]).visible_learners(a)}

    # a superuser still sees the class history
    assert compute_metrics(SimpleNamespace(is_superuser=True), track_id=a_class[0].pk)["tasks"][0]["opened"] == 1


@pytest.mark.django_db
def test_student_page_shows_course_xp_and_no_global_level(two_teachers):
    a, b, public, a_class, b_class = two_teachers
    learner = _user("paged")
    now = timezone.now()
    Progress.objects.create(user=learner, mission=public[1], completed=True, status="completed",
                            started_at=now, last_started_at=now, completed_at=now, xp_earned=10)
    learner.profile.xp = 700
    learner.profile.save(update_fields=["xp"])

    body = _client(a).get(f"/api/teacher/students/{learner.pk}/learning/").json()
    assert body["summary"]["xp"] == 10
    assert body["summary"]["level"] is None and body["summary"]["streak"] is None
    assert body["student"]["level"] is None and body["student"]["xp"] == 10

    own = _client(learner).get("/api/me/learning/").json()
    assert own["summary"]["xp"] == 700 and own["summary"]["level"] is not None


@pytest.mark.django_db
def test_metrics_say_where_left_is_measured(two_teachers):
    a, *_ = two_teachers
    assert compute_metrics(a)["meta"]["activity_scope"] == "own_courses"
    assert compute_metrics(SimpleNamespace(is_superuser=True))["meta"]["activity_scope"] == "platform"


@pytest.mark.django_db
def test_left_for_a_teacher_means_no_work_in_their_courses(two_teachers):
    a, b, public, a_class, b_class = two_teachers
    learner = _user("drifter")
    _join(learner, b_class[0])
    old = timezone.now() - timedelta(days=20)
    TaskProgress.objects.create(user=learner, task=public[2], attempts=1, status="in_progress", last_submitted_at=old)
    LearningEvent.objects.create(user=learner, event_type=LearningEvent.LOGIN)
    CodeRun.objects.create(user=learner, task=b_class[3], outcome="success", duration_ms=1)

    kpi = compute_metrics(a)["kpi"]
    assert kpi["steps_dropped"] == 1  # gone from A's course
    assert compute_metrics(SimpleNamespace(is_superuser=True))["kpi"]["steps_dropped"] == 0  # active on the platform


@pytest.mark.django_db
def test_superuser_namespace_still_works_for_the_pilot(two_teachers):
    pilot = SimpleNamespace(is_superuser=True)
    learner = _user("pilot_l")
    TaskProgress.objects.create(user=learner, task=two_teachers[2][2], attempts=1, status="in_progress",
                                last_submitted_at=timezone.now())
    assert learner.pk in assess_students(pilot)
    assert compute_metrics(pilot)["meta"]["learners"] >= 1
