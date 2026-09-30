"""Personal variants of a step: other numbers and names for every learner, graded on their own."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.test import APIClient

from game.models import Location, Mission, MissionTask, Progress, Track
from game.services import grade_code_run
from game.studio import _clean_variants
from game.variants import fill, personalize, variant_index

User = get_user_model()

pytestmark = pytest.mark.django_db

VARIANTS = [
    {"vars": {"name": "Ари", "n": 7}, "expected_output": "Ари: 28"},
    {"vars": {"name": "Мила", "n": 9}, "expected_output": "Мила: 45"},
]


@pytest.fixture
def task():
    track = Track.objects.create(slug="py", title="Py", is_active=True)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    return MissionTask.objects.create(
        mission=mission,
        order=1,
        task_type="code",
        title_ru="Сумма до {{n}}",
        body_ru="<p>Поприветствуй {{name}} и выведи сумму чисел от 1 до {{n}}.</p>",
        data={
            "starter": "n = {{n}}\n",
            "expected_output": "unused",
            "hidden_check": "assert total({{n}}) == {{n}} * ({{n}} + 1) // 2",
            "hints": [{"ru": "Сложи числа от 1 до {{n}}", "en": "Add 1..{{n}}"}],
            "skeleton": {"ru": "# {{name}}\n", "en": "# {{name}}\n"},
            "variants": VARIANTS,
        },
    )


def _user_with_variant(task, wanted, name):
    """A learner who gets variant *wanted* (users are created until one hashes there)."""
    for i in range(200):
        user = User.objects.create_user(f"{name}{i}", f"{name}{i}@example.com", "S3cure-pass-1")
        if variant_index(user.pk, task.pk, len(VARIANTS)) == wanted:
            return user
        user.delete()
    raise AssertionError("no user found for the variant")


# ── choosing and filling ───────────────────────────────────────────────────


def test_a_step_without_variants_is_returned_untouched():
    plain = MissionTask(pk=1, data={"expected_output": "x"}, body_ru="{{n}}")
    assert personalize(plain, 5) is plain


def test_placeholders_are_filled_everywhere_and_the_original_is_not_changed(task):
    user = _user_with_variant(task, 0, "a")
    mine = personalize(task, user.pk)
    assert mine.title_ru == "Сумма до 7"
    assert "Ари" in mine.body_ru and "{{" not in mine.body_ru
    assert mine.data["starter"] == "n = 7\n"
    assert mine.data["expected_output"] == "Ари: 28"
    assert "7 * (7 + 1)" in mine.data["hidden_check"]
    assert mine.data["hints"][0]["ru"] == "Сложи числа от 1 до 7"
    assert mine.data["skeleton"]["en"] == "# Ари\n"
    assert "variants" not in mine.data
    assert "{{n}}" in task.body_ru and "variants" in task.data  # the stored step keeps its template


def test_the_choice_is_stable_and_everyone_gets_some_variant(task):
    seen = {variant_index(uid, task.pk, 2) for uid in range(1, 40)}
    assert seen == {0, 1}
    assert variant_index(3, task.pk, 2) == variant_index(3, task.pk, 2)


def test_an_anonymous_visitor_sees_the_first_variant(task):
    assert personalize(task, None).data["expected_output"] == "Ари: 28"


def test_unknown_placeholders_stay_as_written():
    assert fill("{{a}} and {{b}}", {"a": 1}) == "1 and {{b}}"


# ── grading on the learner's own variant ───────────────────────────────────


@pytest.fixture
def sandbox(monkeypatch):
    """A sandbox that always succeeds and remembers the scripts it was asked to run."""
    scripts = []

    def fake(script, timeout=None):
        scripts.append(script)
        token = script.rsplit("print(", 1)[1].split(")")[0].strip("'\"")
        return {"status": "success", "output": token}

    monkeypatch.setattr("game.services.execute_python_code", fake)
    return scripts


def test_the_hidden_check_runs_with_the_learners_own_numbers(task, sandbox):
    ari = _user_with_variant(task, 0, "chk")
    Progress.objects.create(user=ari, mission=task.mission, status="in_progress")
    assert grade_code_run(ari, task, "def total(n): return 0", "Ари: 28", 0)["passed"] is True
    assert "assert total(7) == 7 * (7 + 1) // 2" in sandbox[0]


def test_a_learner_passes_with_the_output_of_their_own_variant_only(task, sandbox):
    ari = _user_with_variant(task, 0, "ari")
    mila = _user_with_variant(task, 1, "mila")
    for user in (ari, mila):
        Progress.objects.create(user=user, mission=task.mission, status="in_progress")
    # Mila hands in the answer that belongs to Ari's variant
    assert grade_code_run(mila, task, "print('x')", "Ари: 28", 0)["passed"] is False
    assert grade_code_run(ari, task, "print('x')", "Ари: 28", 0)["passed"] is True
    assert grade_code_run(mila, task, "print('x')", "Мила: 45", 0)["passed"] is True


# ── what the API shows ────────────────────────────────────────────────────


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_the_api_serves_the_learners_own_text_and_no_answer(task):
    mila = _user_with_variant(task, 1, "m")
    rows = _api(mila).get(f"/api/mission-tasks/?mission={task.mission_id}").json()
    row = rows["results"][0] if isinstance(rows, dict) else rows[0]
    assert row["title_ru"] == "Сумма до 9"
    assert "Мила" in row["body_ru"]
    assert row["data"]["starter"] == "n = 9\n"
    dump = str(row)
    assert "variants" not in dump and "Ари: 28" not in dump and "Мила: 45" not in dump


def test_a_hint_speaks_about_the_learners_own_numbers(task):
    ari = _user_with_variant(task, 0, "h")
    ari.profile.hint_scrolls = 2
    ari.profile.save()
    response = _api(ari).post("/api/profile/use-item/", {"item_type": "hint_scrolls", "task_id": task.pk}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["hint"]["text"] == "Сложи числа от 1 до 7"


# ── Studio ─────────────────────────────────────────────────────────────────


def test_studio_keeps_well_formed_variants():
    assert _clean_variants(VARIANTS) == VARIANTS
    assert _clean_variants(None) == []


@pytest.mark.parametrize(
    "bad",
    [
        VARIANTS[:1],  # a single variant is no variation
        "text",
        [{"vars": {}}, {"vars": {}}],
        [{"vars": {"a": 1}}, {"vars": {"b": 2}}],  # different names
        [{"vars": {"a b": 1}}, {"vars": {"a b": 2}}],
        [{"vars": {"a": [1]}}, {"vars": {"a": [2]}}],
        [{"vars": {"a": 1}, "expected_output": 5}, {"vars": {"a": 2}}],
        [{"vars": {"a": "x" * 201}}, {"vars": {"a": "y"}}],
    ],
)
def test_studio_rejects_broken_variants(bad):
    with pytest.raises(serializers.ValidationError):
        _clean_variants(bad)
