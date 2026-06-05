"""Tests for the teacher cabinet roster endpoint (``/api/teacher/students/``).

The cabinet answers "who needs help right now?" for staff. Three things can
break independently and are covered here: the staff-only gate, the roster shape
(non-staff learners only, with the right fields), and the "stuck" rule — a
learner with an *open* (in-progress) mission who is either inactive for too long
or grinding the same mission past the attempt threshold.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import Location, Mission, Progress

User = get_user_model()

URL = "/api/teacher/students/"


def _student(username="stu", *, xp=0, level=1):
    user = User.objects.create_user(username=username, password="TestPass123!")
    user.profile.xp = xp
    user.profile.level = level
    user.profile.save(update_fields=["xp", "level"])
    return user


def _staff(username="teacher", *, superuser=False):
    return User.objects.create_user(
        username=username,
        password="TestPass123!",
        is_staff=True,
        is_superuser=superuser,
    )


def _mission(title="M"):
    loc = Location.objects.create(title="Intro", description="loc")
    return Mission.objects.create(location=loc, title=title, xp_reward=10)


def _open_progress(user, mission, *, attempts=1, last_started=None):
    """An in-progress (not completed) attempt at a mission."""
    return Progress.objects.create(
        user=user,
        mission=mission,
        completed=False,
        status="in_progress",
        attempts=attempts,
        started_at=last_started or timezone.now(),
        last_started_at=last_started or timezone.now(),
    )


def _staff_client(user=None):
    # The cabinet is owner-scoped: a regular teacher sees only students doing
    # their courses. These generic roster/stuck tests assert the *global* view,
    # so they authenticate as the platform owner (superuser), who sees everyone.
    # Per-teacher scoping is covered in test_studio.py.
    client = APIClient()
    client.force_authenticate(user=user or _staff("super", superuser=True))
    return client


# ── Permissions ────────────────────────────────────────────────


@pytest.mark.django_db
def test_anonymous_is_rejected():
    resp = APIClient().get(URL)
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_non_staff_student_is_forbidden():
    client = APIClient()
    client.force_authenticate(user=_student())
    resp = client.get(URL)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_gets_200():
    resp = _staff_client().get(URL)
    assert resp.status_code == 200
    assert "students" in resp.json()
    assert "summary" in resp.json()


# ── Roster shape ───────────────────────────────────────────────


@pytest.mark.django_db
def test_roster_excludes_staff_and_lists_students():
    _staff("admin")
    _student("alice", xp=120, level=2)
    _student("bob", xp=30, level=1)

    body = _staff_client().get(URL).json()
    usernames = {s["username"] for s in body["students"]}
    assert usernames == {"alice", "bob"}  # staff excluded
    assert body["summary"]["total_students"] == 2

    expected = {
        "id",
        "username",
        "display_name",
        "level",
        "xp",
        "current_streak",
        "completed_count",
        "in_progress_count",
        "max_attempts",
        "last_active",
        "stuck",
        "stuck_reason",
    }
    for s in body["students"]:
        assert expected <= set(s.keys())


@pytest.mark.django_db
def test_students_sorted_by_xp_desc():
    _student("low", xp=10)
    _student("high", xp=500)
    body = _staff_client().get(URL).json()
    assert body["students"][0]["username"] == "high"


# ── "Stuck" rule ───────────────────────────────────────────────


@pytest.mark.django_db
def test_inactive_open_mission_is_stuck_inactive():
    """An open mission untouched for >7 days flags the learner as inactive."""
    user = _student("idle")
    old = timezone.now() - timedelta(days=10)
    _open_progress(user, _mission(), attempts=2, last_started=old)

    s = _staff_client().get(URL).json()["students"][0]
    assert s["stuck"] is True
    assert s["stuck_reason"] == "inactive"


@pytest.mark.django_db
def test_many_attempts_open_mission_is_stuck_attempts():
    """Five+ attempts on an unfinished mission flags many_attempts."""
    user = _student("grinder")
    _open_progress(user, _mission(), attempts=5, last_started=timezone.now())

    s = _staff_client().get(URL).json()["students"][0]
    assert s["stuck"] is True
    assert s["stuck_reason"] == "many_attempts"
    assert s["max_attempts"] == 5


@pytest.mark.django_db
def test_recent_low_attempt_open_mission_is_not_stuck():
    """A freshly-started mission with few attempts is normal work, not stuck."""
    user = _student("busy")
    _open_progress(user, _mission(), attempts=2, last_started=timezone.now())

    s = _staff_client().get(URL).json()["students"][0]
    assert s["stuck"] is False
    assert s["stuck_reason"] is None


@pytest.mark.django_db
def test_completed_only_learner_is_not_stuck():
    """No open mission ⇒ never stuck, even if the last activity is old."""
    user = _student("finisher")
    mission = _mission()
    old = timezone.now() - timedelta(days=30)
    Progress.objects.create(
        user=user,
        mission=mission,
        completed=True,
        status="completed",
        attempts=3,
        started_at=old,
        last_started_at=old,
        completed_at=old,
    )

    s = _staff_client().get(URL).json()["students"][0]
    assert s["stuck"] is False
    assert s["completed_count"] == 1
    assert s["in_progress_count"] == 0


@pytest.mark.django_db
def test_summary_counts_stuck_and_active_week():
    """Summary aggregates total, stuck, and 7-day-active learner counts."""
    # Stuck (inactive): open mission, 10 days old.
    stuck = _student("stuck")
    _open_progress(
        stuck, _mission("A"), attempts=1, last_started=timezone.now() - timedelta(days=10)
    )
    # Active & fine: open mission, just now.
    active = _student("active")
    _open_progress(active, _mission("B"), attempts=1, last_started=timezone.now())

    summary = _staff_client().get(URL).json()["summary"]
    assert summary["total_students"] == 2
    assert summary["stuck_count"] == 1
    assert summary["active_week"] == 1  # only the recent one
