"""A solved step pays its own XP (and counts as a day of learning).

The XP the course author typed for a step, the "+XP" the learner sees and the
progress bar used to disagree: step rewards were never granted, only the
mission's completion bonus was. Now the first solve of a step pays it, the
mission bonus stays on top, and the streak counts any solved step.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.models import LeaderboardEntry, Location, Mission, MissionTask, Progress, Track
from game.services import grade_code_run

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user("student", "student@example.com", "S3cure-pass-1")


@pytest.fixture
def client(student):
    api = APIClient()
    api.force_authenticate(student)
    return api


@pytest.fixture
def course():
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1, xp_reward=40)
    story = MissionTask.objects.create(mission=mission, order=1, task_type="story", xp_reward=10)
    quiz = MissionTask.objects.create(
        mission=mission, order=2, task_type="quiz", xp_reward=10, data={"correct_answer": "a"}
    )
    code = MissionTask.objects.create(
        mission=mission, order=3, task_type="code", xp_reward=20, data={"expected_output": "ok"}
    )
    free = MissionTask.objects.create(mission=mission, order=0, task_type="story", xp_reward=0, is_required=False)
    return {"track": track, "mission": mission, "story": story, "quiz": quiz, "code": code, "free": free}


def _submit(client, task, answer=None):
    body = {} if answer is None else {"answer": answer}
    return client.post(f"/api/mission-tasks/{task.id}/submit/", body, format="json")


def _xp(student):
    student.profile.refresh_from_db()
    return student.profile.xp


def test_the_first_correct_answer_pays_the_step_xp(client, student, course):
    _submit(client, course["story"])
    response = _submit(client, course["quiz"], "a").json()
    assert response["progress"]["xp_added"] == 10
    assert _xp(student) == 20


def test_a_wrong_answer_pays_nothing(client, student, course):
    _submit(client, course["story"])
    response = _submit(client, course["quiz"], "b").json()
    assert response["progress"]["xp_added"] == 0
    assert _xp(student) == 10  # only the story step


def test_a_solved_step_never_pays_twice(client, student, course):
    _submit(client, course["story"])
    _submit(client, course["story"])
    assert _xp(student) == 10
    _submit(client, course["quiz"], "a")
    again = _submit(client, course["quiz"], "a").json()
    assert again["progress"]["xp_added"] == 0
    assert _xp(student) == 20


def test_a_passed_code_run_pays_and_a_repeat_run_does_not(student, course):
    verdict = grade_code_run(student, course["code"], "print('ok')", "ok\n", 0)
    assert verdict["progress"]["xp_added"] == 20
    again = grade_code_run(student, course["code"], "print('ok')", "ok\n", 0)
    assert again["progress"]["xp_added"] == 0
    assert _xp(student) == 20


def test_a_failed_code_run_pays_nothing(student, course):
    verdict = grade_code_run(student, course["code"], "print('no')", "no\n", 0)
    assert verdict["passed"] is False
    assert verdict["progress"]["xp_added"] == 0
    assert _xp(student) == 0


def test_a_step_with_zero_xp_pays_nothing_but_still_counts_the_day(client, student, course):
    _submit(client, course["free"])
    assert _xp(student) == 0
    student.profile.refresh_from_db()
    assert student.profile.current_streak == 1


def test_a_level_up_from_a_step_is_reported_and_refills_the_inventory(client, student, course):
    student.profile.xp = 95
    student.profile.save()
    before = (student.profile.hint_scrolls, student.profile.ai_summons)
    payload = _submit(client, course["story"]).json()["progress"]
    assert payload["leveled_up"] is True
    assert payload["new_level"] == 2
    student.profile.refresh_from_db()
    assert (student.profile.hint_scrolls, student.profile.ai_summons) == (before[0] + 1, before[1] + 1)


def test_steps_and_the_mission_bonus_add_up_in_the_mission_progress(client, student, course):
    for key in ("story",):
        _submit(client, course[key])
    _submit(client, course["quiz"], "a")
    grade_code_run(student, course["code"], "print('ok')", "ok\n", 0)
    assert Progress.objects.get(user=student, mission=course["mission"]).xp_earned == 40  # steps only

    done = client.post(f"/api/missions/{course['mission'].pk}/complete/").json()
    assert done["xp_added"] == 40  # the mission bonus
    assert done["first_completion"] is True
    assert done["xp_earned"] == 80  # 40 from steps + 40 bonus
    assert _xp(student) == 80

    replay = client.post(f"/api/missions/{course['mission'].pk}/complete/").json()
    assert replay["first_completion"] is False
    assert _xp(student) == 80


def test_the_streak_counts_a_solved_step_not_only_a_finished_mission(client, student, course):
    _submit(client, course["story"])
    student.profile.refresh_from_db()
    assert student.profile.current_streak == 1
    _submit(client, course["quiz"], "a")  # the same day: no double count
    student.profile.refresh_from_db()
    assert student.profile.current_streak == 1
    assert student.profile.longest_streak == 1


def test_the_leaderboard_follows_the_xp_after_every_step(client, student, course):
    _submit(client, course["story"])
    entry = LeaderboardEntry.objects.get(user=student, scope="global", period_label="all_time")
    assert entry.xp_total == 10
    _submit(client, course["quiz"], "a")
    entry.refresh_from_db()
    assert entry.xp_total == 20
    track_entry = LeaderboardEntry.objects.get(user=student, scope="track", track=course["track"])
    assert track_entry.xp_total == 20


def test_the_step_payload_of_a_read_only_progress_list_is_unchanged(client, student, course):
    """The list endpoint stays read-only and does not need the payout fields."""
    _submit(client, course["story"])
    rows = client.get(f"/api/task-progress/?mission={course['mission'].pk}").json()
    assert rows and "xp_added" not in rows[0]
