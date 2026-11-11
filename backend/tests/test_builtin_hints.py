"""Every quiz step of the built-in courses carries hints, so the Clarity potion has something to give.

The help banner after three failures offered a potion that was switched off ("no ready hint") on all 30
quiz steps. Hints live in ``data.hints`` like on code steps; the 15 ordinary questions have their own, the
15 "explain your solution" questions share the generic ones. The redeploy command copies them into a
running database without touching anything else.
"""

import io
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from game.management.commands.sync_course_protection import FIXTURE_DIR, FIXTURES
from game.models import MissionTask, TaskProgress

User = get_user_model()

pytestmark = pytest.mark.django_db


def _quiz_rows():
    rows = []
    for name in FIXTURES:
        for row in json.loads(Path(FIXTURE_DIR, name).read_text(encoding="utf-8")):
            if row["model"] == "game.missiontask" and row["fields"]["task_type"] == "quiz":
                rows.append(row)
    return rows


def test_there_are_thirty_quiz_steps_and_each_has_two_hints_in_both_languages():
    rows = _quiz_rows()
    assert len(rows) == 30
    for row in rows:
        hints = row["fields"]["data"].get("hints")
        assert isinstance(hints, list) and len(hints) >= 2, row["pk"]
        for hint in hints:
            assert hint["ru"].strip() and hint["en"].strip(), row["pk"]


def test_no_hint_gives_away_the_correct_option():
    for row in _quiz_rows():
        data = row["fields"]["data"]
        if data.get("kind") == "explain":
            continue  # the right answer is a placeholder; the generic hints name no value at all
        right = str(data["correct_answer"]).strip().lower()
        labels = {str(o.get("label", "")).strip().lower() for o in data["options"] if o.get("value") == data["correct_answer"]}
        for hint in data["hints"]:
            for text in (hint["ru"], hint["en"]):
                low = text.lower()
                assert right not in low, (row["pk"], right)
                for label in labels:
                    assert label not in low, (row["pk"], label)


def test_a_seeded_quiz_step_is_marked_as_having_a_hint_and_serves_it():
    call_command("seed_course", verbosity=0)
    task = MissionTask.objects.get(pk=11)
    assert task.task_type == "quiz"
    user = User.objects.create_user("quizzer", "quizzer@example.com", "S3cure-pass-1")
    user.profile.hint_scrolls = 2
    user.profile.save()
    for earlier in MissionTask.objects.filter(mission=task.mission, order__lt=task.order):
        TaskProgress.objects.create(user=user, task=earlier, status="completed")
    api = APIClient()
    api.force_authenticate(user)
    rows = api.get(f"/api/mission-tasks/?mission={task.mission_id}").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    served = next(row for row in rows if row["id"] == task.pk)
    assert served["data"]["has_hint"] is True
    assert "hints" not in served["data"]  # the texts stay on the server until a potion is spent
    first = api.post("/api/profile/use-item/", {"item_type": "hint_scrolls", "task_id": task.pk}, format="json")
    assert first.status_code == 200, first.content
    assert first.json()["hint"]["level"] == 1 and first.json()["hint"]["levels"] == 2


def test_a_redeploy_adds_hints_to_an_existing_database_and_changes_nothing_else():
    call_command("seed_course", verbosity=0)
    quiz = MissionTask.objects.get(pk=11)
    explain = MissionTask.objects.get(pk=23)
    # a database deployed before the hints existed
    for task in (quiz, explain):
        data = dict(task.data)
        data.pop("hints")
        task.data = data
        task.save()
    quiz.refresh_from_db()
    user = User.objects.create_user("learner", "learner@example.com", "S3cure-pass-1")
    TaskProgress.objects.create(user=user, task=quiz, status="completed", attempts=2)

    call_command("sync_course_protection", stdout=io.StringIO())

    quiz.refresh_from_db()
    explain.refresh_from_db()
    assert len(quiz.data["hints"]) == 2 and len(explain.data["hints"]) == 2
    assert quiz.data["correct_answer"] == "str" and len(quiz.data["options"]) == 4
    progress = TaskProgress.objects.get(user=user, task=quiz)
    assert progress.status == "completed" and progress.attempts == 2


def test_hints_written_by_a_teacher_survive_a_redeploy():
    call_command("seed_course", verbosity=0)
    task = MissionTask.objects.get(pk=11)
    task.data = {**task.data, "hints": [{"ru": "Своя подсказка", "en": "My own hint"}]}
    task.save()
    call_command("sync_course_protection", stdout=io.StringIO())
    task.refresh_from_db()
    assert task.data["hints"] == [{"ru": "Своя подсказка", "en": "My own hint"}]
