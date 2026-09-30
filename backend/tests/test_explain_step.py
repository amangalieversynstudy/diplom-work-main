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


# ── explain questions stay out of the research measures ────────────────────


def _miss(user, world, times):
    for wrong in ("1", "4", "3")[:times]:
        _answer(user, world, wrong)


def test_three_wrong_guesses_do_not_put_a_learner_on_the_warning_list(world, teacher):
    from game.warning import early_warning

    user = _learner(world, "k", variant=0)
    _miss(user, world, 3)
    assert early_warning(teacher)["students"] == []


def test_no_help_is_offered_or_logged_for_an_explain_question(world):
    from game.models import LearningEvent

    user = _learner(world, "l", variant=0)
    for wrong in ("1", "4", "3"):
        response = _api(user).post(
            f"/api/mission-tasks/{world['explain'].pk}/submit/", {"answer": wrong}, format="json"
        ).json()
        assert response["progress"]["help_offer"] is None
    assert not LearningEvent.objects.filter(event_type=LearningEvent.HELP_OFFERED).exists()


def test_explain_guesses_do_not_enter_the_failure_curve_or_the_overall_mas(world, teacher):
    user = _learner(world, "m", variant=0)
    _miss(user, world, 3)
    _answer(user, world, "2")
    metrics = compute_metrics(teacher)
    assert metrics["kpi"]["mean_attempts_to_success"] == 1.0  # only the code step (solved at once) counts
    assert all(row["pairs"] <= 1 for row in metrics["help_effect"])
    explain_row = next(row for row in metrics["tasks"] if row["task_id"] == world["explain"].pk)
    assert explain_row["solved"] == 1 and explain_row["mas"] == 4.0


def test_my_journey_does_not_call_explain_guesses_being_stuck(world, teacher):
    from game.me import my_learning

    user = _learner(world, "n", variant=0)
    _miss(user, world, 3)
    picture = my_learning(user)
    assert picture["stuck"] == [] and picture["status"] != "stuck"
    assert picture["attempts"]["solved"] == 1  # the code step only


def test_three_unsolved_explain_questions_do_not_push_real_trouble_off_the_list(world, teacher):
    from game.me import my_learning

    user = _learner(world, "o", variant=0)
    hard = MissionTask.objects.create(mission=world["mission"], order=9, task_type="code", title="Hard")
    TaskProgress.objects.create(user=user, task=hard, status="in_progress", attempts=3)
    for n in range(3):
        extra = MissionTask.objects.create(
            mission=world["mission"], order=10 + n, task_type="quiz", title=f"E{n}",
            data={"kind": "explain", "about": world["code"].pk, "correct_answer": "x", "options": []},
        )
        TaskProgress.objects.create(user=user, task=extra, status="in_progress", attempts=4)
    picture = my_learning(user)
    assert [item["task_id"] for item in picture["stuck"]] == [hard.pk]
    assert picture["status"] == "stuck"


def test_the_risk_model_does_not_count_explain_guesses(world):
    from game.risk import activity_rows

    user = _learner(world, "p", variant=0)
    before = [row for row in activity_rows([user.pk])[user.pk] if row[1]]
    _miss(user, world, 3)
    after = [row for row in activity_rows([user.pk])[user.pk] if row[1]]
    assert len(after) == len(before) == 1  # the code run that solved the step, not the three wrong answers
