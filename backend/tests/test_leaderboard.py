"""The leaderboard lists every learner once.

A learner has a "global" row and a "track" row for each course they have played. The
list endpoint used to return all of them together, so the same name appeared two or
three times in the table the students look at.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import ClassRole, LeaderboardEntry, Location, Mission, MissionTask, Track
from users.models import Profile

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_courses():
    courses = []
    for slug in ("py-one", "py-two"):
        track = Track.objects.create(slug=slug, title=slug, is_active=True)
        location = Location.objects.create(track=track, title="L", order=1)
        mission = Mission.objects.create(location=location, title="M", order=1, xp_reward=10)
        task = MissionTask.objects.create(mission=mission, order=1, task_type="story", xp_reward=10)
        courses.append((track, task))
    return courses


@pytest.fixture
def played(two_courses):
    """One learner who has solved a step in both courses."""
    user = User.objects.create_user("learner", "learner@example.com", "S3cure-pass-1")
    api = APIClient()
    api.force_authenticate(user)
    for _, task in two_courses:
        assert api.post(f"/api/mission-tasks/{task.id}/submit/", {}, format="json").status_code == 200
    return user


def test_the_rows_exist_for_every_scope(played):
    scopes = sorted(LeaderboardEntry.objects.filter(user=played).values_list("scope", flat=True))
    assert scopes == ["global", "track", "track"]


def test_the_default_list_has_each_learner_once(played):
    rows = APIClient().get("/api/leaderboard/").json()
    assert [row["scope"] for row in rows] == ["global"]
    assert rows[0]["xp"] == 20


def test_a_course_filter_returns_that_course_table(played, two_courses):
    slug = two_courses[1][0].slug
    rows = APIClient().get(f"/api/leaderboard/?track={slug}").json()
    assert [(row["scope"], row["track"]["slug"], row["xp_total"]) for row in rows] == [("track", slug, 10)]


def test_a_course_table_shows_the_xp_of_that_course_not_the_total(played, two_courses):
    slug = two_courses[1][0].slug
    row = APIClient().get(f"/api/leaderboard/?track={slug}").json()[0]
    assert row["xp"] == 10  # the learner has 20 XP in all, 10 of them here


def test_the_scope_can_still_be_asked_for_explicitly(played):
    rows = APIClient().get("/api/leaderboard/?scope=track").json()
    assert {row["scope"] for row in rows} == {"track"}
    assert len(rows) == 2


def test_a_class_is_reported_by_pk_and_by_name(played):
    role = ClassRole.objects.create(name="Mage")
    played.profile.class_role = role
    played.profile.save()
    row = APIClient().get("/api/leaderboard/").json()[0]
    assert (row["class_role_id"], row["class_role"]) == (role.pk, "Mage")


def test_a_learner_without_a_class_has_none(played):
    row = APIClient().get("/api/leaderboard/").json()[0]
    assert row["class_role_id"] is None and row["class_role"] is None


def test_the_list_costs_the_same_queries_for_one_learner_or_many(played):
    client = APIClient()
    role = ClassRole.objects.create(name="Mage")

    def queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/api/leaderboard/").status_code == 200
        return len(ctx)

    alone = queries()
    for i in range(8):
        user = User.objects.create_user(f"other{i}", f"o{i}@example.com", "S3cure-pass-1")
        user.profile.class_role = role
        user.profile.save()
        LeaderboardEntry.objects.create(user=user, scope="global", period_label="all_time", xp_total=i)
    assert queries() == alone


def test_a_lapsed_streak_reads_zero_and_does_not_win_a_tie():
    today = timezone.localdate()
    lapsed = User.objects.create_user("aaa-lapsed", "a@example.com", "S3cure-pass-1")
    Profile.objects.filter(user=lapsed).update(current_streak=9, last_streak_date=today - timedelta(days=3))
    live = User.objects.create_user("zzz-live", "z@example.com", "S3cure-pass-1")
    Profile.objects.filter(user=live).update(current_streak=2, last_streak_date=today)
    for user in (lapsed, live):
        LeaderboardEntry.objects.create(user=user, scope="global", period_label="all_time", xp_total=50)
    rows = APIClient().get("/api/leaderboard/").json()
    assert [(row["username"], row["streak"]) for row in rows] == [("zzz-live", 2), ("aaa-lapsed", 0)]
