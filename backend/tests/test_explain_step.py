"""'Explain your solution': a personalised quiz question after a code step, and what the teacher learns from it."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from game.authorship import authorship_report
from game.footprint import finish_code_run
from game.metrics import compute_metrics
from game.models import Location, Mission, MissionTask, Progress, TaskProgress, Track
from game.variants import variant_index

User = get_user_model()

pytestmark = pytest.mark.django_db

VARIANTS = [
    {"vars": {"o1": "1", "o2": "2", "o3": "3", "o4": "4", "right": "2", "k": 5}},
    {"vars": {"o1": "1", "o2": "2", "o3": "3", "o4": "4", "right": "3", "k": 6}},
]


@pytest.fixture
def teacher():
    return User.objects.create_user("teacher", "t@example.com", "S3cure-pass-1", is_staff=True)


@pytest.fixture
def world(teacher):
    track = Track.objects.create(slug="mine", title="Mine", is_active=True, owner=teacher)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    code = MissionTask.objects.create(
        mission=mission, order=1, task_type="code", title="Loop", data={"expected_output": "ok"}
    )
    explain = MissionTask.objects.create(
        mission=mission,
        order=2,
        task_type="quiz",
        title_ru="Объясни",
        body_ru="<p>Сколько раз при {{k}}?</p>",
        data={
            "kind": "explain",
            "about": code.pk,
            "correct_answer": "{{right}}",
            "options": [{"value": f"{{{{o{i}}}}}", "label": f"{{{{o{i}}}}}"} for i in range(1, 5)],
            "variants": VARIANTS,
        },
    )
    return {"mission": mission, "code": code, "explain": explain}


def _learner(world, name, variant=None):
    """A learner who solved the code step, with the wanted variant of the explain question."""
    for i in range(300):
        user = User.objects.create_user(f"{name}{i}", f"{name}{i}@example.com", "S3cure-pass-1")
        if variant is None or variant_index(user.pk, world["explain"].pk, 2) == variant:
            break
        user.delete()
    Progress.objects.create(user=user, mission=world["mission"], status="in_progress")
    finish_code_run(
        user, world["code"], code="print('ok')\n", stdout="ok", stderr="", exit_code=0,
        duration=0.1, reasons=set(), provenance={"typed_chars": 12, "pasted_chars": 0, "elapsed_ms": 30000},
    )
    return user


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _answer(user, world, value):
    response = _api(user).post(f"/api/mission-tasks/{world['explain'].pk}/submit/", {"answer": value}, format="json")
    assert response.status_code == 200, response.content
    return response.json()["correct"]


def test_the_step_is_an_explain_kind_not_a_plain_quiz(world):
    assert world["explain"].kind == "explain"
    assert world["code"].kind == "code"
    assert MissionTask(task_type="quiz", data={}).kind == "quiz"


def test_each_learner_is_graded_on_their_own_variant(world):
    first = _learner(world, "a", variant=0)   # the right answer is "2"
    second = _learner(world, "b", variant=1)  # the right answer is "3"
    assert _answer(first, world, "3") is False
    assert _answer(first, world, "2") is True
    assert _answer(second, world, "2") is False
    assert _answer(second, world, "3") is True


def test_the_learner_sees_their_own_options_and_no_key(world):
    user = _learner(world, "c", variant=1)
    rows = _api(user).get(f"/api/mission-tasks/?mission={world['mission'].pk}").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    row = next(r for r in rows if r["id"] == world["explain"].pk)
    assert "Сколько раз при 6?" in row["body_ru"]
    assert [o["value"] for o in row["data"]["options"]] == ["1", "2", "3", "4"]
    assert "correct_answer" not in row["data"] and "variants" not in row["data"]


def test_the_analytics_keep_explain_questions_apart_from_quizzes(world, teacher):
    user = _learner(world, "d", variant=0)
    _answer(user, world, "2")
    funnel = {row["task_type"]: row for row in compute_metrics(teacher)["funnel"]}
    assert funnel["explain"]["steps"] == 1 and funnel["explain"]["solved"] == 1
    assert funnel["quiz"]["steps"] == 0


# ── what the teacher sees ──────────────────────────────────────────────────


def _row(user, teacher):
    return authorship_report(user, teacher)["steps"][0]


def test_no_answer_yet_is_reported_as_none(world, teacher):
    user = _learner(world, "e", variant=0)
    assert _row(user, teacher)["explain"] == {"status": "none", "wrong": 0}


def test_a_first_try_answer_and_a_retry_are_told_apart(world, teacher):
    quick = _learner(world, "f", variant=0)
    _answer(quick, world, "2")
    assert _row(quick, teacher)["explain"] == {"status": "first_try", "wrong": 0}
    slow = _learner(world, "g", variant=0)
    _answer(slow, world, "1")
    _answer(slow, world, "4")
    _answer(slow, world, "2")
    assert _row(slow, teacher)["explain"] == {"status": "retried", "wrong": 2}


def test_an_unsolved_question_counts_the_wrong_answers(world, teacher):
    user = _learner(world, "h", variant=0)
    _answer(user, world, "1")
    assert _row(user, teacher)["explain"] == {"status": "unsolved", "wrong": 1}


def test_missing_the_question_twice_adds_a_signal_only_next_to_another_one(world, teacher):
    user = _learner(world, "i", variant=0)
    _answer(user, world, "1")
    _answer(user, world, "3")
    assert all(s["code"] != "explain_missed" for s in _row(user, teacher)["signals"])  # typed code: nothing else stands out
    # the same learner's solving run now looks pasted
    from game.models import CodeRun

    CodeRun.objects.filter(user=user).update(provenance={"pasted_chars": 200, "typed_chars": 0, "paste_count": 1,
                                                          "edits_after_paste": 0, "elapsed_ms": 4000}, code_length=210)
    codes = [s["code"] for s in _row(user, teacher)["signals"]]
    assert "paste_then_run" in codes and "explain_missed" in codes


def test_a_code_step_without_an_explain_question_has_none(teacher, world):
    world["explain"].delete()
    user = _learner(world, "j")
    assert _row(user, teacher)["explain"] is None


# ── Studio cannot break the question ───────────────────────────────────────


def test_editing_an_explain_step_in_the_studio_keeps_its_data(world, teacher):
    client = _api(teacher)
    response = client.patch(
        f"/api/teacher/studio/tasks/{world['explain'].pk}/",
        {"title_ru": "Новое название", "data": {"options": [{"value": "a", "label": "a"}, {"value": "b", "label": "b"}], "correct_answer": "a"}},
        format="json",
    )
    assert response.status_code == 200, response.content
    task = MissionTask.objects.get(pk=world["explain"].pk)
    assert task.title_ru == "Новое название"
    assert task.data["kind"] == "explain" and len(task.data["variants"]) == 2
    assert task.data["correct_answer"] == "{{right}}"
