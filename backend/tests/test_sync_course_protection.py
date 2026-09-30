"""sync_course_protection: protection reaches a running database without reloading the whole course."""

import io

import pytest
from django.core.management import call_command

from game.models import MissionTask, Progress, TaskProgress
from game.management.commands.sync_course_protection import protected_steps

pytestmark = pytest.mark.django_db


def _seed():
    call_command("seed_course", stdout=io.StringIO())


def _run(*args):
    out = io.StringIO()
    call_command("sync_course_protection", *args, stdout=out)
    return out.getvalue()


def _strip_protection(pk):
    """Make a step look like it was deployed before the protection existed."""
    task = MissionTask.objects.get(pk=pk)
    data = {k: v for k, v in task.data.items() if k not in ("not_yet", "variants")}
    task.data = data
    task.body_ru = "старый текст"
    task.save()


def test_thirteen_steps_carry_protection():
    # 13 steps have not_yet (missions 1-13); the nine with variants are among them
    steps = protected_steps()
    assert len(steps) == 13
    assert sum("variants" in f["data"] for f in steps.values()) == 9


def test_a_fresh_database_is_already_protected():
    _seed()
    assert "0 step(s)" in _run()


def test_an_old_database_gets_the_protection_and_nothing_else_changes():
    _seed()
    _strip_protection(22)
    task = MissionTask.objects.get(pk=22)
    task.xp_reward, task.order = 77, 5
    task.save()
    out = _run()
    assert "step 22: updated" in out and "changed 1 step(s)" in out
    task.refresh_from_db()
    assert len(task.data["variants"]) == 6 and task.data["not_yet"]
    assert "{{mana}}" in task.data["starter"] and "{{mana}}" in task.body_ru
    assert (task.xp_reward, task.order) == (77, 5)


def test_dry_run_changes_nothing():
    _seed()
    _strip_protection(32)
    out = _run("--dry-run")
    assert "step 32: would update" in out and "would change 1 step(s)" in out
    assert "variants" not in MissionTask.objects.get(pk=32).data
    assert MissionTask.objects.get(pk=32).body_ru == "старый текст"


def test_a_step_that_already_has_protection_is_left_alone_unless_forced():
    _seed()
    task = MissionTask.objects.get(pk=42)
    task.body_ru = "правка преподавателя"
    task.save()
    assert "step 42: already protected" in _run()
    assert MissionTask.objects.get(pk=42).body_ru == "правка преподавателя"
    assert "step 42: updated" in _run("--force")
    assert "{{base}}" in MissionTask.objects.get(pk=42).body_ru


def test_progress_survives():
    from django.contrib.auth import get_user_model

    _seed()
    user = get_user_model().objects.create_user("u", "u@example.com", "S3cure-pass-1")
    task = MissionTask.objects.get(pk=52)
    progress = Progress.objects.create(user=user, mission=task.mission)
    TaskProgress.objects.create(user=user, task=task, status="completed", attempts=2)
    _strip_protection(52)
    _run()
    assert TaskProgress.objects.get(user=user, task=task).status == "completed"
    assert Progress.objects.filter(pk=progress.pk).exists()


def test_a_database_without_a_step_skips_it():
    _seed()
    MissionTask.objects.filter(pk=62).delete()
    assert "step 62: not in this database" in _run()


def test_a_missing_explain_question_is_created_with_its_fixture_id():
    _seed()
    MissionTask.objects.filter(pk=23).delete()
    out = _run("--dry-run")
    assert "explain step 23: would create" in out
    assert not MissionTask.objects.filter(pk=23).exists()
    assert "explain step 23: created" in _run()
    step = MissionTask.objects.get(pk=23)
    assert step.kind == "explain" and step.data["about"] == 22 and step.mission_id == 2
    assert "explain step 23: present" in _run()


def test_an_explain_question_whose_mission_is_missing_is_skipped():
    _seed()
    from game.models import Mission

    Mission.objects.filter(pk=2).delete()
    assert "explain step 23: its mission is not in this database" in _run()
