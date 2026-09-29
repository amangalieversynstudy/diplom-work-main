"""Server-side grading: the browser is never trusted to say "I solved it"."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.models import (
    LeaderboardEntry,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)
from game.services import grade_code_run, public_task_data

User = get_user_model()

pytestmark = pytest.mark.django_db

SECRETS = ("correct_answer", "expected_output", "sampleOutput", "isCorrect", "Charged")


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
    """Published track: mission with story -> quiz -> code steps."""
    track = Track.objects.create(slug="python", title="Python", is_active=True)
    location = Location.objects.create(track=track, title="Island", order=1)
    mission = Mission.objects.create(
        location=location, title="Basics", order=1, xp_reward=100
    )
    story = MissionTask.objects.create(
        mission=mission, order=1, task_type="story", title="Story", body="Read me"
    )
    quiz = MissionTask.objects.create(
        mission=mission,
        order=2,
        task_type="quiz",
        title="Quiz",
        data={
            "correct_answer": "str",
            "options": [
                {"value": "str", "label": "str", "isCorrect": True},
                {"value": "int", "label": "int"},
            ],
        },
    )
    code = MissionTask.objects.create(
        mission=mission,
        order=3,
        task_type="code",
        title="Code",
        data={
            "language": "python",
            "starter": "def mana_status(m):\n    pass\n",
            "sampleOutput": "Charged",
            "expected_output": "Charged",
        },
    )
    return track, location, mission, story, quiz, code


def submit(client, task, answer=None):
    body = {} if answer is None else {"answer": answer}
    return client.post(f"/api/mission-tasks/{task.id}/submit/", body, format="json")


def solve_all(client, student, mission):
    """Solve every required step (code through the same service the runner uses)."""
    for task in mission.tasks.filter(is_required=True).order_by("order", "id"):
        if task.task_type == "code":
            grade_code_run(student, task, "print('Charged')", "Charged\n", 0)
        elif task.task_type == "quiz":
            assert submit(client, task, "str").json()["correct"] is True
        else:
            assert submit(client, task).status_code == 200


# ── the answer key stays on the server ──────────────────────────────────────


def test_public_task_data_keeps_only_safe_keys(course):
    _, _, _, _, quiz, code = course
    assert public_task_data(quiz) == {
        "options": [{"value": "str", "label": "str"}, {"value": "int", "label": "int"}]
    }
    assert public_task_data(code) == {
        "language": "python",
        "starter": "def mana_status(m):\n    pass\n",
    }


@pytest.mark.parametrize(
    "path",
    [
        "/api/mission-tasks/?mission={mission}",
        "/api/missions/{mission}/",
        "/api/missions/",
        "/api/tracks/",
        "/api/locations/",
    ],
)
def test_no_public_endpoint_leaks_answers(course, path):
    _, _, mission, *_ = course
    body = APIClient().get(path.format(mission=mission.id)).content.decode()
    assert "Basics" in body or "Story" in body or "Python" in body  # real payload
    for secret in SECRETS:
        assert secret not in body, f"{secret!r} leaked via {path}"


def test_starter_code_and_option_labels_are_still_public(course):
    _, _, mission, *_ = course
    body = APIClient().get(f"/api/missions/{mission.id}/").content.decode()
    assert "def mana_status" in body
    assert '"label": "int"' in body or '"label":"int"' in body


# ── quiz / story submission ─────────────────────────────────────────────────


def test_story_step_is_completed_by_the_server(client, student, course):
    _, _, _, story, *_ = course
    response = submit(client, story)
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is True
    assert body["progress"]["status"] == "completed"
    assert body["progress"]["attempts"] == 1
    assert body["progress"]["best_score"] == 100


def test_wrong_quiz_answer_counts_an_attempt_but_does_not_complete(
    client, student, course
):
    _, _, _, story, quiz, _ = course
    submit(client, story)
    response = submit(client, quiz, "int")
    assert response.status_code == 200
    assert response.json()["correct"] is False
    progress = TaskProgress.objects.get(user=student, task=quiz)
    assert (progress.status, progress.attempts, progress.best_score) == (
        "in_progress",
        1,
        0,
    )
    assert progress.answer == {"selected": "int"}


def test_quiz_answer_is_case_and_space_insensitive_and_counts_attempts(
    client, student, course
):
    _, _, _, story, quiz, _ = course
    submit(client, story)
    submit(client, quiz, "int")
    response = submit(client, quiz, "  STR ")
    assert response.json()["correct"] is True
    progress = TaskProgress.objects.get(user=student, task=quiz)
    assert (progress.status, progress.attempts, progress.best_score) == (
        "completed",
        2,
        100,
    )


def test_attempts_stop_counting_after_the_first_success(client, student, course):
    _, _, _, story, quiz, _ = course
    submit(client, story)
    submit(client, quiz, "str")
    submit(client, quiz, "int")  # a later wrong click must not undo the solve
    progress = TaskProgress.objects.get(user=student, task=quiz)
    assert (progress.status, progress.attempts) == ("completed", 1)


@pytest.mark.parametrize("answer", [None, "", "   ", ["str"], {"a": 1}, True])
def test_quiz_needs_a_plain_answer(client, course, answer):
    _, _, _, story, quiz, _ = course
    submit(client, story)
    assert submit(client, quiz, answer).status_code == 400


def test_quiz_without_an_answer_key_is_never_accepted(client, course):
    _, _, _, story, quiz, _ = course
    quiz.data = {"options": [{"value": "a", "label": "a"}]}
    quiz.save()
    submit(client, story)
    assert submit(client, quiz, "a").status_code == 400


def test_code_steps_are_not_accepted_over_plain_rest(client, course):
    _, _, _, story, quiz, code = course
    submit(client, story)
    submit(client, quiz, "str")
    assert submit(client, code, "print('Charged')").status_code == 400
    assert not TaskProgress.objects.filter(task=code, status="completed").exists()


def test_steps_must_be_done_in_order(client, course):
    _, _, _, story, quiz, _ = course
    assert submit(client, quiz, "str").status_code == 409
    assert not TaskProgress.objects.filter(task=quiz).exists()
    assert submit(client, story).status_code == 200
    assert submit(client, quiz, "str").status_code == 200


def test_optional_steps_do_not_block_later_ones(client, course):
    _, _, mission, story, quiz, _ = course
    story.is_required = False
    story.save()
    assert submit(client, quiz, "str").status_code == 200


def test_submit_requires_login(course):
    _, _, _, story, *_ = course
    assert submit(APIClient(), story).status_code == 401


def test_submit_respects_level_and_prerequisites(client, student, course):
    _, location, mission, story, *_ = course
    locked = Mission.objects.create(
        location=location, title="Locked", order=2, min_level=5
    )
    locked_story = MissionTask.objects.create(mission=locked, task_type="story", order=1)
    assert submit(client, locked_story).status_code == 403

    gated = Mission.objects.create(location=location, title="Gated", order=3)
    gated.prerequisites.add(mission)
    gated_story = MissionTask.objects.create(mission=gated, task_type="story", order=1)
    assert submit(client, gated_story).status_code == 403

    inactive = Mission.objects.create(
        location=location, title="Off", order=4, is_active=False
    )
    inactive_story = MissionTask.objects.create(
        mission=inactive, task_type="story", order=1
    )
    assert submit(client, inactive_story).status_code == 400


# ── progress cannot be written by the client ────────────────────────────────


def test_task_progress_endpoint_is_read_only(client, student, course):
    _, _, _, story, *_ = course
    submit(client, story)
    row = TaskProgress.objects.get(user=student, task=story)
    url = f"/api/task-progress/{row.id}/"
    assert client.post("/api/task-progress/", {"task": story.id}, format="json").status_code == 405
    assert client.patch(url, {"best_score": 999}, format="json").status_code == 405
    assert client.put(url, {"task": story.id}, format="json").status_code == 405
    assert client.delete(url).status_code == 405
    row.refresh_from_db()
    assert row.best_score == 100


def test_task_progress_lists_only_own_rows_and_filters_by_mission(
    client, student, course
):
    _, location, mission, story, *_ = course
    submit(client, story)
    other_mission = Mission.objects.create(location=location, title="Other", order=2)
    other_story = MissionTask.objects.create(
        mission=other_mission, task_type="story", order=1
    )
    submit(client, other_story)
    stranger = User.objects.create_user("stranger", "s2@example.com", "S3cure-pass-2")
    TaskProgress.objects.create(user=stranger, task=story, status="completed")

    rows = client.get(f"/api/task-progress/?mission={mission.id}").json()
    assert [r["task"] for r in rows] == [story.id]
    assert len(client.get("/api/task-progress/").json()) == 2
    assert client.get("/api/task-progress/?mission=abc").json() == []


def test_junk_mission_filter_does_not_crash_the_task_list(course):
    response = APIClient().get("/api/mission-tasks/?mission=abc")
    assert response.status_code == 200
    assert response.json() == []


def test_progress_endpoint_is_read_only(client, student, course):
    _, _, mission, story, *_ = course
    submit(client, story)
    client.post(f"/api/missions/{mission.id}/start/")
    row = Progress.objects.get(user=student, mission=mission)
    url = f"/api/progress/{row.id}/"
    assert client.get(url).status_code == 200
    assert client.patch(url, {"xp_earned": 99999, "completed": True}, format="json").status_code == 405
    assert client.delete(url).status_code == 405
    assert client.post("/api/progress/", {"mission": mission.id}, format="json").status_code == 405
    row.refresh_from_db()
    assert (row.xp_earned, row.completed) == (0, False)


# ── completing a mission ────────────────────────────────────────────────────


def test_mission_without_tasks_cannot_be_completed(client, course):
    _, location, *_ = course
    empty = Mission.objects.create(location=location, title="Empty", order=5, xp_reward=999)
    assert client.post(f"/api/missions/{empty.id}/complete/").status_code == 409


def test_mission_cannot_be_completed_before_its_tasks_are_solved(client, student, course):
    _, _, mission, story, *_ = course
    submit(client, story)
    response = client.post(f"/api/missions/{mission.id}/complete/")
    assert response.status_code == 409
    student.profile.refresh_from_db()
    assert student.profile.xp == 0
    assert not Progress.objects.filter(user=student, mission=mission, completed=True).exists()


def test_completing_after_solving_everything_awards_xp_once(client, student, course):
    _, _, mission, *_ = course
    solve_all(client, student, mission)
    first = client.post(f"/api/missions/{mission.id}/complete/")
    assert first.status_code == 200
    assert first.json()["xp_added"] == 100
    assert first.json()["stars"] == 3
    again = client.post(f"/api/missions/{mission.id}/complete/")
    assert again.json()["xp_added"] == 0
    student.profile.refresh_from_db()
    assert student.profile.xp == 100


def test_stars_come_from_the_server_not_the_request(client, student, course):
    _, _, mission, story, quiz, code = course
    submit(client, story)
    for _ in range(2):
        submit(client, quiz, "int")  # two wrong tries
    submit(client, quiz, "str")
    grade_code_run(student, code, "print('Charged')", "Charged\n", 0)
    response = client.post(
        f"/api/missions/{mission.id}/complete/", {"stars": 3}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["stars"] == 2


@pytest.mark.parametrize("junk", ["abc", None, [1], {"a": 1}, -5, 99])
def test_junk_stars_are_ignored_instead_of_crashing(client, student, course, junk):
    _, _, mission, *_ = course
    solve_all(client, student, mission)
    response = client.post(
        f"/api/missions/{mission.id}/complete/", {"stars": junk}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["stars"] == 3


def test_leaderboard_matches_profile_xp_right_after_completion(client, student, course):
    _, _, mission, *_ = course
    solve_all(client, student, mission)
    client.post(f"/api/missions/{mission.id}/complete/")
    student.profile.refresh_from_db()
    entry = LeaderboardEntry.objects.get(user=student, scope="global", track=None)
    assert entry.xp_total == student.profile.xp == 100
    track_entry = LeaderboardEntry.objects.get(user=student, scope="track")
    assert track_entry.xp_total == 100


# ── draft (unpublished) tracks ──────────────────────────────────────────────


@pytest.fixture
def draft(course):
    track = Track.objects.create(slug="draft", title="Draft", is_active=False)
    location = Location.objects.create(track=track, title="Draft island", order=1)
    mission = Mission.objects.create(
        location=location, title="Draft mission", order=1, xp_reward=500
    )
    task = MissionTask.objects.create(mission=mission, task_type="story", order=1)
    return track, location, mission, task


def test_draft_content_is_hidden_from_learners(client, draft):
    _, location, mission, task = draft
    titles = [m["title"] for m in client.get("/api/missions/").json()]
    assert "Draft mission" not in titles
    assert client.get(f"/api/missions/{mission.id}/").status_code == 404
    assert client.get("/api/locations/").json() == [] or all(
        loc["id"] != location.id for loc in client.get("/api/locations/").json()
    )
    tasks = client.get(f"/api/mission-tasks/?mission={mission.id}").json()
    assert tasks == []


def test_draft_missions_cannot_be_started_solved_or_completed(client, student, draft):
    _, _, mission, task = draft
    assert client.post(f"/api/missions/{mission.id}/start/").status_code == 404
    assert submit(client, task).status_code == 404
    assert client.post(f"/api/missions/{mission.id}/complete/").status_code == 404
    student.profile.refresh_from_db()
    assert student.profile.xp == 0


def test_superuser_can_still_see_drafts(draft):
    _, _, mission, _ = draft
    admin = User.objects.create_superuser("boss", "boss@example.com", "S3cure-pass-9")
    api = APIClient()
    api.force_authenticate(admin)
    assert api.get(f"/api/missions/{mission.id}/").status_code == 200


# ── grading code runs (used by the WebSocket runner) ────────────────────────


def _run(student, task, stdout, exit_code=0, code="print('x')"):
    return grade_code_run(student, task, code, stdout, exit_code)


def test_matching_output_passes_and_is_recorded(student, course):
    *_, code = course
    verdict = _run(student, code, "Charged\n")
    assert verdict["passed"] is True
    assert verdict["progress"]["status"] == "completed"
    assert verdict["progress"]["attempts"] == 1
    assert verdict["progress"]["answer"] == {"code": "print('x')"}


@pytest.mark.parametrize(
    "stdout, exit_code",
    [("Charged\n", 1), ("Wrong\n", 0), ("", 0), ("Charged\nextra\n", 0)],
)
def test_wrong_output_or_failed_run_does_not_pass(student, course, stdout, exit_code):
    *_, code = course
    verdict = _run(student, code, stdout, exit_code)
    assert verdict["passed"] is False
    assert verdict["progress"]["status"] == "in_progress"
    assert verdict["progress"]["best_score"] == 0


def test_output_comparison_ignores_line_endings_and_trailing_space(student, course):
    *_, code = course
    assert _run(student, code, "  Charged \r\n")["passed"] is True


def test_attempts_until_success_are_counted_then_frozen(student, course):
    *_, code = course
    assert _run(student, code, "nope")["progress"]["attempts"] == 1
    assert _run(student, code, "", exit_code=1)["progress"]["attempts"] == 2
    assert _run(student, code, "Charged")["progress"]["attempts"] == 3
    later = _run(student, code, "broken", exit_code=1)
    assert later["progress"]["attempts"] == 3
    assert later["progress"]["status"] == "completed"


def test_code_task_without_expected_output_passes_on_a_clean_run(student, course):
    _, _, mission, *_ = course
    practice = MissionTask.objects.create(
        mission=mission, order=9, task_type="code", data={"starter": "print('hi')"}
    )
    assert _run(student, practice, "hi\n")["passed"] is True
    other = MissionTask.objects.create(
        mission=mission, order=10, task_type="code", data={"starter": "x"}
    )
    assert _run(student, other, "", exit_code=1)["passed"] is False


def test_first_graded_attempt_starts_the_mission(student, course):
    _, _, mission, story, *_ = course
    assert not Progress.objects.filter(user=student, mission=mission).exists()
    _run(student, story, "")
    progress = Progress.objects.get(user=student, mission=mission)
    assert progress.status == "in_progress"
    assert progress.started_at is not None
