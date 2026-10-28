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
    assert MissionTask.objects.filter(mission__location__track=track).count() == 30


def test_the_second_course_follows_the_intro_and_does_not_gate_class_selection():
    _seed()
    intro = Track.objects.get(slug="python-intro")
    second = Track.objects.get(slug="python-continued")
    assert second.is_intro is False
    assert Track.get_intro() == intro  # class selection still opens after the first course
    missions = list(Mission.objects.filter(location__track=second).order_by("order"))
    assert len(missions) == 8
    assert MissionTask.objects.filter(mission__location__track=second).count() == 32
    # the first mission of the second course waits for the last one of the intro
    last_intro = Mission.objects.filter(location__track=intro).order_by("order").last()
    assert list(missions[0].prerequisites.all()) == [last_intro]
    # and every later mission waits for the one before it
    for before, after in zip(missions, missions[1:]):
        assert list(after.prerequisites.all()) == [before]


def test_an_existing_deployment_gets_the_second_course_on_the_next_boot():
    call_command("loaddata", "ranks", "class_roles", "intro_course", verbosity=0)
    assert not Track.objects.filter(slug="python-continued").exists()
    _seed()
    assert Track.objects.filter(slug="python-continued").exists()


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


def test_a_forced_reload_keeps_the_course_owner():
    from django.contrib.auth import get_user_model

    _seed()
    teacher = get_user_model().objects.create_user("teacher", "t@example.com", "S3cure-pass-1", is_staff=True)
    Track.objects.filter(slug="python-intro").update(owner=teacher)
    _seed("--force")
    assert Track.objects.get(slug="python-intro").owner_id == teacher.pk


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
    """The deploy start must not delete content or swallow seeding errors; it runs `release` in one process."""
    from pathlib import Path

    from django.conf import settings

    from game.management.commands.release import STEPS

    root = Path(settings.BASE_DIR).parent
    dockerfile = (root / "Dockerfile.backend").read_text(encoding="utf-8")
    toml = (root / "railway.toml").read_text(encoding="utf-8")
    steps = [name for name, _ in STEPS]
    assert steps[0] == "migrate" and "seed_course" in steps
    assert "sync_course_protection" in steps  # a running database gets the variants and explain steps too
    assert "manage.py release && exec daphne" in dockerfile
    assert "startCommand" not in toml  # the image's CMD is the start command; the healthcheck waits for it
    assert 'healthcheckPath = "/healthz"' in toml
    for text in (dockerfile, toml):
        assert "loaddata" not in text and ".delete()" not in text and "|| true" not in text


def test_release_runs_every_step_in_one_process(monkeypatch):
    from django.core.management import call_command

    from game.management.commands import release

    called = []
    monkeypatch.setattr(release, "call_command", lambda name, **kw: called.append(name))
    call_command("release")
    assert called == [name for name, _ in release.STEPS]
