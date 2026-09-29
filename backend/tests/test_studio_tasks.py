"""Studio: teachers author the tasks of their missions (story / quiz / code)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.models import Location, Mission, MissionTask, Track

User = get_user_model()

pytestmark = pytest.mark.django_db

TASKS = "/api/teacher/studio/tasks/"
MISSIONS = "/api/teacher/studio/missions/"


def _client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def _teacher(name="teacher"):
    return User.objects.create_user(username=name, password="TestPass123!", is_staff=True)


def _mission(owner, title="Mission", **extra):
    track = Track.objects.create(slug=f"t-{owner.username}-{title}", title="T", owner=owner)
    location = Location.objects.create(track=track, title="Section")
    return Mission.objects.create(location=location, title=title, is_active=False, **extra)


QUIZ = {
    "options": [{"value": "str", "label": "str"}, {"value": "int", "label": "int"}],
    "correct_answer": "str",
}


def _task(api, mission, **fields):
    payload = {"mission": mission.pk, "task_type": "story", "title_ru": "Шаг", "order": 1}
    payload.update(fields)
    return api.post(TASKS, payload, format="json")


# ── authoring ───────────────────────────────────────────────────────────────


def test_teacher_adds_the_three_kinds_of_step():
    teacher = _teacher()
    mission = _mission(teacher)
    api = _client(teacher)

    story = _task(api, mission, body_ru="<p>Читай</p>")
    quiz = _task(api, mission, task_type="quiz", order=2, data=QUIZ)
    code = _task(api, mission, task_type="code", order=3, data={"starter": "x = 1", "expected_output": "1"})
    assert (story.status_code, quiz.status_code, code.status_code) == (201, 201, 201)
    assert story.json()["data"] == {}
    assert code.json()["data"] == {"language": "python", "starter": "x = 1", "expected_output": "1"}
    # the legacy columns the play side falls back to are filled too
    task = MissionTask.objects.get(pk=story.json()["id"])
    assert task.title == "Шаг" and task.body == "<p>Читай</p>"


def test_only_story_quiz_and_code_can_be_authored():
    teacher = _teacher()
    response = _task(_client(teacher), _mission(teacher), task_type="project")
    assert response.status_code == 400 and "task_type" in response.json()


@pytest.mark.parametrize(
    "data",
    [
        {"options": [{"value": "a"}], "correct_answer": "a"},  # one option
        {"options": [{"value": "a"}, {"value": "b"}], "correct_answer": "c"},  # key not an option
        {"options": [{"value": "a"}, {"value": "A"}], "correct_answer": "a"},  # duplicates
        {"options": [{"value": "a"}, {"value": " "}], "correct_answer": "a"},  # empty value
        {"options": "a,b", "correct_answer": "a"},
        {"options": [{"value": str(n)} for n in range(9)], "correct_answer": "1"},  # too many
    ],
)
def test_a_quiz_must_be_answerable(data):
    teacher = _teacher()
    response = _task(_client(teacher), _mission(teacher), task_type="quiz", data=data)
    assert response.status_code == 400 and "data" in response.json()


def test_the_answer_keeps_the_authors_spelling():
    teacher = _teacher()
    data = {"options": [{"value": "Str"}, {"value": "int"}], "correct_answer": "str"}
    response = _task(_client(teacher), _mission(teacher), task_type="quiz", data=data)
    assert response.json()["data"]["correct_answer"] == "Str"


def test_a_step_needs_a_title_and_sane_numbers():
    teacher = _teacher()
    mission, api = _mission(teacher), _client(teacher)
    assert api.post(TASKS, {"mission": mission.pk, "task_type": "story"}, format="json").status_code == 400
    assert _task(api, mission, xp_reward=101).status_code == 400
    assert _task(api, mission, xp_reward=-1).status_code == 400
    assert _task(api, mission, estimated_minutes=0).status_code == 400
    assert _task(api, mission, body_ru="x" * 20_001).status_code == 400


def test_updating_a_quiz_revalidates_it():
    teacher = _teacher()
    mission, api = _mission(teacher), _client(teacher)
    task_id = _task(api, mission, task_type="quiz", data=QUIZ).json()["id"]
    bad = api.patch(f"{TASKS}{task_id}/", {"data": {**QUIZ, "correct_answer": "float"}}, format="json")
    assert bad.status_code == 400
    ok = api.patch(f"{TASKS}{task_id}/", {"title_ru": "Новое"}, format="json")
    assert ok.status_code == 200 and MissionTask.objects.get(pk=task_id).title == "Новое"


# ── ownership ───────────────────────────────────────────────────────────────


def test_teachers_only_touch_their_own_missions():
    mine, other = _teacher("mine"), _teacher("other")
    theirs = _mission(other)
    api = _client(mine)
    assert _task(api, theirs).status_code == 403

    existing = MissionTask.objects.create(mission=theirs, order=1, task_type="story", title="x")
    assert api.get(TASKS).json() in ([], {"count": 0, "next": None, "previous": None, "results": []})
    assert api.patch(f"{TASKS}{existing.pk}/", {"title_ru": "hack"}, format="json").status_code == 404
    assert api.delete(f"{TASKS}{existing.pk}/").status_code == 404


def test_a_task_cannot_be_moved_into_a_foreign_mission():
    mine, other = _teacher("mine"), _teacher("other")
    api = _client(mine)
    task_id = _task(api, _mission(mine, "Own")).json()["id"]
    moved = api.patch(f"{TASKS}{task_id}/", {"mission": _mission(other, "Theirs").pk}, format="json")
    assert moved.status_code == 403


def test_the_studio_is_closed_to_learners_and_anonymous_users():
    learner = User.objects.create_user(username="learner", password="TestPass123!")
    assert _client(learner).get(TASKS).status_code == 403
    assert APIClient().get(TASKS).status_code in (401, 403)


def test_superuser_sees_every_task():
    teacher = _teacher()
    _task(_client(teacher), _mission(teacher))
    boss = User.objects.create_user(username="boss", password="x" * 12, is_staff=True, is_superuser=True)
    body = _client(boss).get(TASKS).json()
    assert len(body["results"] if isinstance(body, dict) else body) == 1


# ── publishing and rewards ──────────────────────────────────────────────────


def test_a_mission_without_tasks_cannot_be_published():
    teacher = _teacher()
    track = Track.objects.create(slug="c", title="C", owner=teacher)
    location = Location.objects.create(track=track, title="S")
    api = _client(teacher)

    created = api.post(MISSIONS, {"location": location.pk, "title_ru": "M"}, format="json")
    assert created.status_code == 201 and created.json()["is_active"] is False
    direct = api.post(MISSIONS, {"location": location.pk, "title_ru": "M2", "is_active": True}, format="json")
    assert direct.status_code == 400 and "is_active" in direct.json()

    mission_id = created.json()["id"]
    assert api.patch(f"{MISSIONS}{mission_id}/", {"is_active": True}, format="json").status_code == 400
    _task(api, Mission.objects.get(pk=mission_id))
    assert api.patch(f"{MISSIONS}{mission_id}/", {"is_active": True}, format="json").status_code == 200


def test_removing_the_last_task_unpublishes_the_mission():
    teacher = _teacher()
    mission, api = _mission(teacher), _client(teacher)
    first = _task(api, mission).json()["id"]
    second = _task(api, mission, order=2).json()["id"]
    Mission.objects.filter(pk=mission.pk).update(is_active=True)

    api.delete(f"{TASKS}{first}/")
    assert Mission.objects.get(pk=mission.pk).is_active is True
    api.delete(f"{TASKS}{second}/")
    assert Mission.objects.get(pk=mission.pk).is_active is False


def test_rewards_are_capped():
    teacher = _teacher()
    track = Track.objects.create(slug="c", title="C", owner=teacher)
    location = Location.objects.create(track=track, title="S")
    api = _client(teacher)
    for xp in (501, -5):
        response = api.post(
            MISSIONS, {"location": location.pk, "title_ru": "M", "xp_reward": xp}, format="json"
        )
        assert response.status_code == 400 and "xp_reward" in response.json()
    assert api.post(
        MISSIONS, {"location": location.pk, "title_ru": "M", "xp_reward": 500}, format="json"
    ).status_code == 201


# ── the whole path: teacher authors, learner finishes ───────────────────────


def test_a_learner_can_finish_a_mission_a_teacher_built_in_the_studio():
    teacher = _teacher()
    api = _client(teacher)
    track_id = api.post("/api/teacher/studio/tracks/", {"title_ru": "Курс"}, format="json").json()["id"]
    location_id = api.post(
        "/api/teacher/studio/locations/", {"track": track_id, "title_ru": "Раздел"}, format="json"
    ).json()["id"]
    mission_id = api.post(
        MISSIONS, {"location": location_id, "title_ru": "Первая", "xp_reward": 40}, format="json"
    ).json()["id"]
    mission = Mission.objects.get(pk=mission_id)
    story = _task(api, mission, body_ru="Привет").json()["id"]
    quiz = _task(api, mission, task_type="quiz", order=2, data=QUIZ).json()["id"]
    assert api.patch(f"{MISSIONS}{mission_id}/", {"is_active": True}, format="json").status_code == 200
    assert api.patch(f"/api/teacher/studio/tracks/{track_id}/", {"is_active": True}, format="json").status_code == 200

    learner = User.objects.create_user(username="learner", password="TestPass123!")
    student = _client(learner)
    listed = student.get("/api/mission-tasks/", {"mission": mission_id}).json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert {r["id"] for r in rows} == {story, quiz}
    assert "correct_answer" not in str(rows)  # the key stays with the author

    assert student.post(f"/api/mission-tasks/{story}/submit/").status_code == 200
    wrong = student.post(f"/api/mission-tasks/{quiz}/submit/", {"answer": "int"}, format="json").json()
    assert wrong["correct"] is False
    right = student.post(f"/api/mission-tasks/{quiz}/submit/", {"answer": "STR"}, format="json").json()
    assert right["correct"] is True
    done = student.post(f"/api/missions/{mission_id}/complete/", {}, format="json")
    assert done.status_code == 200 and done.json()["xp_added"] == 40
