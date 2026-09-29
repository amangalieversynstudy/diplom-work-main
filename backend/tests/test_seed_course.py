"""seed_course must seed a fresh database and never clobber existing content."""

import pytest
from django.core.management import call_command

from game.models import ClassRole, Mission, MissionTask, Rank, Track

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_course", *args, verbosity=0)


def test_seeds_an_empty_database():
    _seed()
    assert Rank.objects.count() == 5
    assert ClassRole.objects.count() == 3
    track = Track.objects.get(slug="python-intro")
    assert track.is_intro is True
    assert Mission.objects.filter(location__track=track).count() == 8
    assert MissionTask.objects.filter(mission__location__track=track).count() == 23


def test_second_run_changes_nothing():
    _seed()
    before = (Rank.objects.count(), Mission.objects.count(), MissionTask.objects.count())
    _seed()
    after = (Rank.objects.count(), Mission.objects.count(), MissionTask.objects.count())
    assert before == after


def test_author_edits_survive_a_restart():
    """The deploy start command runs seed_course on every boot."""
    _seed()
    mission = Mission.objects.order_by("id").first()
    mission.title_ru = "Правка преподавателя"
    mission.xp_reward = 7
    mission.save()
    task = MissionTask.objects.order_by("id").first()
    task.title_ru = "Правка задачи"
    task.save()
    Rank.objects.filter(pk=1).update(title_ru="Свой ранг")

    _seed()

    mission.refresh_from_db()
    task.refresh_from_db()
    assert mission.title_ru == "Правка преподавателя"
    assert mission.xp_reward == 7
    assert task.title_ru == "Правка задачи"
    assert Rank.objects.get(pk=1).title_ru == "Свой ранг"


def test_deleted_task_is_not_resurrected_by_a_restart():
    _seed()
    task = MissionTask.objects.order_by("id").first()
    task_id = task.id
    task.delete()
    _seed()
    assert not MissionTask.objects.filter(pk=task_id).exists()


def test_only_missing_fixtures_are_loaded():
    Rank.objects.create(id=1, slug="custom", title_en="Custom", title_ru="Свой")
    _seed()
    assert Rank.objects.count() == 1  # ranks untouched
    assert Rank.objects.get().slug == "custom"
    assert Track.objects.filter(slug="python-intro").exists()  # course seeded
    assert ClassRole.objects.count() == 3


def test_force_restores_the_fixture_version():
    _seed()
    mission = Mission.objects.order_by("id").first()
    original_title = mission.title_ru
    mission.title_ru = "Правка преподавателя"
    mission.save()

    _seed("--force")

    mission.refresh_from_db()
    assert mission.title_ru == original_title


def test_railway_start_command_seeds_safely():
    """The deploy command must not delete content or swallow seeding errors."""
    from pathlib import Path

    from django.conf import settings

    toml = (Path(settings.BASE_DIR).parent / "railway.toml").read_text(encoding="utf-8")
    assert "seed_course" in toml
    assert "loaddata" not in toml
    assert ".delete()" not in toml
    assert "|| true" not in toml
