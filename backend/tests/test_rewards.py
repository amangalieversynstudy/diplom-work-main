"""Who earns what: teachers try courses for free, an own course or an unvetted class cannot be farmed."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import (
    Enrollment,
    LeaderboardEntry,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    Track,
    UserAchievement,
)

User = get_user_model()


def _user(name, **extra):
    return User.objects.create_user(username=name, password="RewardPass123!", **extra)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _course(owner, slug, *, public, xp=500, step_xp=100):
    track = Track.objects.create(slug=slug, title=slug, owner=owner, is_public=public)
    location = Location.objects.create(track=track, title="L")
    mission = Mission.objects.create(location=location, title=f"M {slug}", xp_reward=xp)
    step = MissionTask.objects.create(mission=mission, order=1, task_type="story", title="Story", xp_reward=step_xp)
    return track, mission, step


def _play(user, mission, step):
    client = _client(user)
    assert client.post(f"/api/missions/{mission.pk}/start/").status_code == 200
    solved = client.post(f"/api/mission-tasks/{step.pk}/submit/", {}, format="json").json()["progress"]
    done = client.post(f"/api/missions/{mission.pk}/complete/", {}, format="json").json()
    return solved, done


@pytest.mark.django_db
def test_an_owner_playing_their_own_course_earns_nothing():
    teacher = _user("farmer", is_teacher=True)
    _, mission, step = _course(teacher, "own", public=False)
    solved, done = _play(teacher, mission, step)

    assert solved["xp_added"] == 0 and done["xp_added"] == 0 and done["leveled_up"] is False
    teacher.profile.refresh_from_db()
    assert teacher.profile.xp == 0 and teacher.profile.level == 1
    assert teacher.profile.current_streak == 0
    assert not LeaderboardEntry.objects.filter(user=teacher).exists()
    assert not UserAchievement.objects.filter(user=teacher).exists()
    # the trial run is still graded
    assert Progress.objects.get(user=teacher, mission=mission).completed


@pytest.mark.django_db
def test_an_unvetted_class_pays_class_xp_only():
    teacher = _user("self_t", is_teacher=True)
    track, mission, step = _course(teacher, "self-class", public=False, xp=40, step_xp=100)
    learner = _user("pupil")
    Enrollment.objects.create(user=learner, track=track, consented_at=timezone.now())
    hints, summons = learner.profile.hint_scrolls, learner.profile.ai_summons

    solved, done = _play(learner, mission, step)

    assert solved["xp_added"] == 100 and solved["counts_globally"] is False
    assert done["xp_added"] == 40 and done["counts_globally"] is False
    learner.profile.refresh_from_db()
    assert learner.profile.xp == 0 and learner.profile.level == 1
    assert (learner.profile.hint_scrolls, learner.profile.ai_summons) == (hints, summons)
    assert Progress.objects.get(user=learner, mission=mission).xp_earned == 140
    assert LeaderboardEntry.objects.get(user=learner, scope="track", track=track).xp_total == 140
    assert not LeaderboardEntry.objects.filter(user=learner, scope="global").exists()
    assert not UserAchievement.objects.filter(user=learner).exists()
    # class learners keep their streak (one day at a time, it cannot be sped up)
    assert learner.profile.current_streak == 1


@pytest.mark.django_db
def test_a_vetted_teachers_class_and_public_courses_pay_as_before():
    staff = _user("staff_t", is_staff=True)
    track, mission, step = _course(staff, "staff-class", public=False, xp=40, step_xp=10)
    learner = _user("pupil2")
    Enrollment.objects.create(user=learner, track=track, consented_at=timezone.now())

    solved, done = _play(learner, mission, step)

    assert solved["counts_globally"] is True and done["counts_globally"] is True
    learner.profile.refresh_from_db()
    assert learner.profile.xp == 50
    assert LeaderboardEntry.objects.filter(user=learner, scope="global").exists()
    assert UserAchievement.objects.filter(user=learner, slug="first_mission").exists()


@pytest.mark.django_db
def test_completing_a_finished_mission_again_has_no_side_effects():
    learner = _user("again")
    _, mission, step = _course(None, "public-again", public=True, xp=20, step_xp=5)
    _play(learner, mission, step)
    progress = Progress.objects.get(user=learner, mission=mission)
    Progress.objects.filter(pk=progress.pk).update(completed_at=timezone.now() - timedelta(minutes=5))
    events = LearningEvent.objects.filter(user=learner, event_type=LearningEvent.MISSION_COMPLETED).count()

    again = _client(learner).post(f"/api/missions/{mission.pk}/complete/", {}, format="json")

    assert again.status_code == 200
    assert again.json()["xp_added"] == 0 and again.json()["deduplicated"] is True
    assert LearningEvent.objects.filter(user=learner, event_type=LearningEvent.MISSION_COMPLETED).count() == events


@pytest.mark.django_db
def test_the_leaderboard_lists_no_teachers_and_drops_learners_who_left_a_class():
    staff = _user("lb_staff", is_staff=True)
    teacher = _user("lb_teacher", is_teacher=True)
    learner, leaver = _user("lb_l"), _user("lb_leaver")
    for user in (staff, teacher, learner):
        LeaderboardEntry.objects.create(user=user, scope="global", period_label="all_time", xp_total=50)
    track, _, _ = _course(staff, "lb-class", public=False)
    member = Enrollment.objects.create(user=learner, track=track, consented_at=timezone.now())
    gone = Enrollment.objects.create(user=leaver, track=track, consented_at=timezone.now())
    for user in (learner, leaver):
        LeaderboardEntry.objects.create(user=user, scope="track", track=track, period_label="all_time", xp_total=9)
    gone.delete()
    assert member.pk

    global_rows = APIClient().get("/api/leaderboard/").json()
    assert [r["username"] for r in global_rows] == ["lb_l"]
    class_rows = _client(learner).get("/api/leaderboard/", {"scope": "track"}).json()
    assert [r["username"] for r in class_rows] == ["lb_l"]
    # a closed class's row carries no platform-wide values
    assert class_rows[0]["level"] is None and class_rows[0]["streak"] is None and class_rows[0]["xp"] == 9


@pytest.mark.django_db
def test_a_single_leaderboard_row_does_not_crash():
    learner = _user("lb_one")
    row = LeaderboardEntry.objects.create(user=learner, scope="global", period_label="all_time", xp_total=5)
    assert APIClient().get(f"/api/leaderboard/{row.pk}/").status_code == 200


@pytest.mark.django_db
def test_level_up_items_are_capped_without_taking_any_away():
    learner = _user("rich")
    profile = learner.profile
    profile.add_xp(10_000)
    profile.refresh_from_db()
    assert profile.hint_scrolls <= 30 and profile.ai_summons <= 20

    profile.hint_scrolls, profile.ai_summons = 50, 40
    profile.save(update_fields=["hint_scrolls", "ai_summons"])
    profile.add_xp(500)
    profile.refresh_from_db()
    assert (profile.hint_scrolls, profile.ai_summons) == (50, 40)
