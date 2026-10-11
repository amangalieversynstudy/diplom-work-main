"""Inventory items must help with the step in front of the learner.

The hint potion used to answer every learner with the same sentence about
indentation and the architect scroll pasted the starter code a second time.
Now the author's own hints and outline are served by the server, one level per
potion, and an item is never spent when there is nothing to give.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.models import LearningEvent, Location, Mission, MissionTask, Track

User = get_user_model()

pytestmark = pytest.mark.django_db

USE = "/api/profile/use-item/"

HINTS = [
    {"ru": "Сначала разбери самый большой случай.", "en": "Start with the biggest case."},
    {"ru": "Диапазон пишется через >=.", "en": "A range is written with >=."},
]
SKELETON = {"ru": "def f(x):\n    # 1. проверь\n    pass\n", "en": "def f(x):\n    # 1. check\n    pass\n"}


@pytest.fixture
def student():
    user = User.objects.create_user("student", "student@example.com", "S3cure-pass-1")
    user.profile.hint_scrolls = 5
    user.profile.skeleton_scrolls = 5
    user.profile.save()
    return user


@pytest.fixture
def api(student):
    client = APIClient()
    client.force_authenticate(student)
    return client


@pytest.fixture
def steps():
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    helped = MissionTask.objects.create(
        mission=mission, order=1, task_type="code",
        data={"starter": "x", "hints": HINTS, "skeleton": SKELETON},
    )
    bare = MissionTask.objects.create(mission=mission, order=2, task_type="code", data={"starter": "y"})
    return {"mission": mission, "helped": helped, "bare": bare}


def _use(api, item, task, **headers):
    return api.post(USE, {"item_type": item, "task_id": task.pk}, format="json", **headers)


def test_each_potion_reveals_the_next_level_of_the_hint(api, student, steps):
    first = _use(api, "hint_scrolls", steps["helped"]).json()
    second = _use(api, "hint_scrolls", steps["helped"]).json()
    third = _use(api, "hint_scrolls", steps["helped"]).json()
    assert first["hint"] == {"text": HINTS[0]["ru"], "level": 1, "levels": 2}
    assert second["hint"]["text"] == HINTS[1]["ru"]
    # after the last level the learner keeps the deepest hint instead of an empty potion
    assert third["hint"]["text"] == HINTS[1]["ru"]
    assert third["remaining"] == 2
    assert LearningEvent.objects.filter(user=student, event_type="hint_used", task=steps["helped"]).count() == 3


def test_a_step_without_hints_costs_nothing(api, student, steps):
    response = _use(api, "hint_scrolls", steps["bare"])
    assert response.status_code == 409
    assert response.json()["code"] == "no_hint"
    student.profile.refresh_from_db()
    assert student.profile.hint_scrolls == 5
    assert not LearningEvent.objects.filter(user=student, event_type="hint_used").exists()


def test_a_hint_needs_a_step(api, student):
    response = api.post(USE, {"item_type": "hint_scrolls"}, format="json")
    assert response.status_code == 409
    student.profile.refresh_from_db()
    assert student.profile.hint_scrolls == 5


def test_the_architect_scroll_gives_the_authors_outline(api, student, steps):
    response = _use(api, "skeleton_scrolls", steps["helped"])
    assert response.status_code == 200
    assert response.json()["skeleton"] == SKELETON["ru"].strip()
    assert response.json()["remaining"] == 4


def test_a_step_without_an_outline_does_not_spend_the_scroll(api, student, steps):
    response = _use(api, "skeleton_scrolls", steps["bare"])
    assert response.status_code == 409
    assert response.json()["code"] == "no_skeleton"
    student.profile.refresh_from_db()
    assert student.profile.skeleton_scrolls == 5


def test_the_text_follows_the_interface_language(api, steps):
    response = _use(api, "hint_scrolls", steps["helped"], HTTP_ACCEPT_LANGUAGE="en")
    assert response.json()["hint"]["text"] == HINTS[0]["en"]


def test_a_missing_translation_falls_back_to_the_other_language(api, steps):
    steps["helped"].data = {"starter": "x", "hints": [{"ru": "Только по-русски"}]}
    steps["helped"].save()
    response = _use(api, "hint_scrolls", steps["helped"], HTTP_ACCEPT_LANGUAGE="en")
    assert response.json()["hint"]["text"] == "Только по-русски"


def test_the_public_task_only_says_that_help_exists(steps):
    client = APIClient()
    body = client.get(f"/api/missions/{steps['mission'].pk}/").content.decode()
    assert '"has_hint": true' in body.replace('":true', '": true')
    assert '"has_skeleton": true' in body.replace('":true', '": true')
    for secret in (HINTS[0]["ru"], HINTS[1]["en"], "# 1. проверь"):
        assert secret not in body


def test_a_step_without_help_advertises_none(steps):
    from game.services import public_task_data

    assert "has_hint" not in public_task_data(steps["bare"])
    assert "has_skeleton" not in public_task_data(steps["bare"])


def test_an_unknown_item_is_still_refused(api):
    response = api.post(USE, {"item_type": "gold"}, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("path", ["/api/ai-assist/", "/api/ai-mentor/"])
def test_the_ai_outage_message_does_not_expose_the_configuration(api, settings, monkeypatch, path):
    settings.GEMINI_API_KEY = ""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    payload = {"task_description": "t"} if "assist" in path else {"messages": [{"role": "user", "content": "help"}]}
    response = api.post(path, payload, format="json")
    text = str(response.json())
    assert "GEMINI" not in text and "Ключ" not in text
    assert "Мудрец" in text


@pytest.mark.parametrize("path", ["/api/ai-assist/", "/api/ai-mentor/"])
@pytest.mark.parametrize("bad", [{"language": "x" * 33}, {"language": ["python"]}, {"code": 5}, {"task_description": ["t"]}])
def test_ai_requests_with_oversized_or_non_string_fields_are_refused_not_500(api, path, bad):
    payload = {"task_description": "t", "messages": [{"role": "user", "content": "help"}], **bad}
    assert api.post(path, payload, format="json").status_code == 400


# ── Studio: authors write the hints and the outline ─────────────────────────


@pytest.fixture
def teacher_api():
    teacher = User.objects.create_user(username="teacher", password="TestPass123!", is_staff=True)
    track = Track.objects.create(slug="tt", title="T", owner=teacher)
    location = Location.objects.create(track=track, title="Section")
    mission = Mission.objects.create(location=location, title="Mission", is_active=False)
    api = APIClient()
    api.force_authenticate(teacher)
    return api, mission


def _author(api, mission, **data):
    return api.post(
        "/api/teacher/studio/tasks/",
        {
            "mission": mission.pk,
            "task_type": "code",
            "title_ru": "Шаг",
            "order": 1,
            "data": {"starter": "", "expected_output": "4", **data},
        },
        format="json",
    )


def test_a_teacher_can_write_hints_and_an_outline(teacher_api):
    api, mission = teacher_api
    response = _author(api, mission, hints=HINTS, skeleton=SKELETON)
    assert response.status_code == 201, response.content
    data = response.json()["data"]
    assert data["hints"] == HINTS
    assert data["skeleton"] == {"ru": SKELETON["ru"].strip(), "en": SKELETON["en"].strip()}


def test_empty_hints_and_outlines_are_not_stored(teacher_api):
    api, mission = teacher_api
    response = _author(api, mission, hints=[{"ru": "  ", "en": ""}], skeleton={"ru": "", "en": ""})
    assert response.status_code == 201
    assert "hints" not in response.json()["data"]
    assert "skeleton" not in response.json()["data"]


def test_too_many_or_too_long_hints_are_refused(teacher_api):
    api, mission = teacher_api
    assert _author(api, mission, hints=[{"ru": str(n)} for n in range(6)]).status_code == 400
    assert _author(api, mission, hints=[{"ru": "x" * 501}]).status_code == 400
    assert _author(api, mission, hints="not a list").status_code == 400


def test_a_hint_written_by_a_teacher_reaches_the_learner(teacher_api, student, api):
    teacher, mission = teacher_api
    created = _author(teacher, mission, hints=HINTS).json()
    task = MissionTask.objects.get(pk=created["id"])
    response = _use(api, "hint_scrolls", task)
    assert response.status_code == 200
    assert response.json()["hint"]["text"] == HINTS[0]["ru"]


# ---- free rescue hint: a stuck learner with an empty inventory still gets a way forward ----

def _stuck(student, task, failures=3):
    from game.models import TaskProgress

    TaskProgress.objects.create(user=student, task=task, status="in_progress", attempts=failures)


def _empty(student):
    student.profile.hint_scrolls = 0
    student.profile.ai_summons = 0
    student.profile.save()


def test_rescue_hint_is_free_once_and_logged_separately(api, student, steps):
    _empty(student)
    _stuck(student, steps["helped"])
    first = _use(api, "rescue_hint", steps["helped"])
    assert first.status_code == 200
    assert first.json()["hint"]["text"] == HINTS[0]["ru"]
    student.profile.refresh_from_db()
    assert student.profile.hint_scrolls == 0  # nothing was charged or granted
    assert LearningEvent.objects.filter(user=student, event_type=LearningEvent.HELP_RESCUE).count() == 1
    assert not LearningEvent.objects.filter(user=student, event_type=LearningEvent.HINT_USED).exists()
    assert _use(api, "rescue_hint", steps["helped"]).status_code == 409  # once per step


def test_rescue_hint_needs_the_offer_and_an_empty_inventory(api, student, steps):
    _empty(student)
    _stuck(student, steps["helped"], failures=2)
    assert _use(api, "rescue_hint", steps["helped"]).status_code == 409  # not stuck yet
    from game.models import TaskProgress

    TaskProgress.objects.filter(user=student).update(attempts=3)
    student.profile.hint_scrolls = 1
    student.profile.save()
    assert _use(api, "rescue_hint", steps["helped"]).status_code == 409  # has a scroll: use it
