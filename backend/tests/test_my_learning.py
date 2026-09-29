"""The learner's own progress screen (``GET /api/me/learning/``)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import (
    CodeRun,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)

User = get_user_model()

pytestmark = pytest.mark.django_db

URL = "/api/me/learning/"


def _user(name):
    return User.objects.create_user(name, f"{name}@example.com", "S3cure-pass-1")


def _api(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


@pytest.fixture
def student():
    return _user("student")


@pytest.fixture
def course():
    """Two missions; the second needs the first. Story, quiz, code in the first."""
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    location = Location.objects.create(track=track, title="L", order=1)
    first = Mission.objects.create(location=location, title="First", order=1)
    second = Mission.objects.create(location=location, title="Second", order=2)
    second.prerequisites.add(first)
    story = MissionTask.objects.create(mission=first, order=1, task_type="story", title="Story")
    quiz = MissionTask.objects.create(
        mission=first, order=2, task_type="quiz", title="Quiz", data={"correct_answer": "a"}
    )
    code = MissionTask.objects.create(mission=first, order=3, task_type="code", title="Code")
    later = MissionTask.objects.create(mission=second, order=1, task_type="story", title="Later")
    return {"first": first, "second": second, "story": story, "quiz": quiz, "code": code, "later": later}


def _solve(user, task, attempts=1):
    return TaskProgress.objects.create(
        user=user, task=task, status="completed", attempts=attempts,
        last_submitted_at=timezone.now(),
    )


def _get(user):
    response = _api(user).get(URL)
    assert response.status_code == 200, response.content
    return response.json()


def test_it_needs_a_login():
    assert APIClient().get(URL).status_code in (401, 403)


def test_a_new_learner_is_pointed_at_the_first_step(student, course):
    data = _get(student)
    assert data["status"] == "new"
    assert data["next"]["task_id"] == course["story"].pk
    assert data["summary"]["steps_total"] == 4
    assert data["summary"]["steps_done"] == 0
    assert data["stuck"] == [] and data["review"] == []


def test_progress_counts_solved_steps_and_missions(student, course):
    _solve(student, course["story"])
    _solve(student, course["quiz"])
    data = _get(student)
    assert data["summary"]["steps_done"] == 2
    row = next(m for m in data["missions"] if m["id"] == course["first"].pk)
    assert (row["steps_done"], row["steps_total"], row["completed"]) == (2, 3, False)
    assert data["next"]["task_id"] == course["code"].pk


def test_the_next_mission_waits_for_its_prerequisite(student, course):
    for key in ("story", "quiz", "code"):
        _solve(student, course[key])
    # every step of the first mission is solved but the mission is not completed yet
    assert _get(student)["next"] is None  # the second mission is still closed
    Progress.objects.create(user=student, mission=course["first"], completed=True)
    assert _get(student)["next"]["task_id"] == course["later"].pk


def test_a_step_with_repeated_failures_is_listed_and_marks_the_learner_as_stuck(student, course):
    TaskProgress.objects.create(user=student, task=course["code"], status="in_progress", attempts=4)
    TaskProgress.objects.create(user=student, task=course["quiz"], status="in_progress", attempts=1)
    data = _get(student)
    assert data["status"] == "stuck"
    assert [item["task_id"] for item in data["stuck"]] == [course["code"].pk, course["quiz"].pk]
    assert data["stuck"][0]["attempts"] == 4


def test_a_step_solved_only_after_many_tries_is_suggested_for_review(student, course):
    _solve(student, course["quiz"], attempts=5)
    _solve(student, course["code"], attempts=1)
    data = _get(student)
    assert [item["task_id"] for item in data["review"]] == [course["quiz"].pk]


def test_a_learner_who_stopped_coming_is_called_away(student, course):
    TaskProgress.objects.create(user=student, task=course["code"], status="in_progress", attempts=1)
    old = timezone.now() - timedelta(days=6)
    TaskProgress.objects.filter(user=student).update(last_submitted_at=old)
    run = CodeRun.objects.create(user=student, task=course["code"], outcome="error", duration_ms=5)
    CodeRun.objects.filter(pk=run.pk).update(created_at=old)
    data = _get(student)
    assert data["status"] == "away"
    assert data["summary"]["days_away"] >= 5


def test_quick_solvers_get_the_great_status(student, course):
    for key in ("story", "quiz", "code"):
        _solve(student, course[key], attempts=1)
    data = _get(student)
    assert data["status"] == "great"
    assert data["attempts"]["mine"] == 1
    assert data["attempts"]["first_try_share"] == 100


def test_the_cohort_average_stays_hidden_while_the_group_is_small(student, course):
    _solve(student, course["quiz"], attempts=2)
    for n in range(3):
        _solve(_user(f"peer{n}"), course["quiz"], attempts=3)
    data = _get(student)
    assert data["attempts"]["cohort"] is None
    assert data["attempts"]["cohort_size"] is None


def test_the_cohort_average_shows_once_enough_others_have_solved(student, course):
    _solve(student, course["quiz"], attempts=2)
    for n in range(5):
        _solve(_user(f"peer{n}"), course["quiz"], attempts=3)
    data = _get(student)
    assert data["attempts"]["cohort"] == 3
    assert data["attempts"]["cohort_size"] == 5


def test_other_learners_data_never_appears(student, course):
    other = _user("other")
    TaskProgress.objects.create(user=other, task=course["code"], status="in_progress", attempts=6)
    data = _get(student)
    assert data["stuck"] == []
    assert "other" not in str(data)


def test_a_risk_probability_is_never_shown(student, course):
    TaskProgress.objects.create(user=student, task=course["code"], status="in_progress", attempts=5)
    text = str(_get(student)).lower()
    assert "risk" not in text and "probab" not in text


def test_activity_covers_two_weeks_with_runs_and_solved_steps(student, course):
    CodeRun.objects.create(user=student, task=course["code"], outcome="ok", duration_ms=5)
    _solve(student, course["quiz"])
    activity = _get(student)["activity"]
    assert len(activity) == 14
    assert activity[-1]["runs"] == 1
    assert activity[-1]["solved"] == 1


def test_draft_tracks_are_not_part_of_the_learners_course(student, course):
    draft = Track.objects.create(slug="draft", title="Draft", is_active=False)
    location = Location.objects.create(track=draft, title="D", order=1)
    hidden = Mission.objects.create(location=location, title="Hidden", order=1)
    MissionTask.objects.create(mission=hidden, order=1, task_type="story")
    data = _get(student)
    assert all(m["id"] != hidden.pk for m in data["missions"])
    assert data["summary"]["steps_total"] == 4


def test_titles_follow_the_requested_language(student, course):
    course["story"].title_en = "Story EN"
    course["story"].title_ru = "Сюжет"
    course["story"].save()
    api = _api(student)
    assert api.get(URL, {"lang": "en"}).json()["next"]["title"] == "Story EN"
    assert api.get(URL, {"lang": "ru"}).json()["next"]["title"] == "Сюжет"
