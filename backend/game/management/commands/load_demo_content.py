"""Management command to seed demo locations and missions.

This command is intended for local/dev environments to quickly populate
the database with two locations and three missions (including a repeatable
one) for manual testing. In non-debug environments it requires the
environment variable ALLOW_DEMO_SEED=true to proceed.
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from game.models import Location, Mission, Track


class Command(BaseCommand):
    """Load demo locations and missions for quick manual testing."""

    help = "Load demo locations and missions for quick manual testing"

    def handle(self, *args, **options):
        """Execute command: create locations, missions and prerequisites."""
        allow_env = os.getenv("ALLOW_DEMO_SEED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not settings.DEBUG and not allow_env:
            self.stdout.write(
                self.style.WARNING(
                    "Demo seeding is disabled in non-debug environments. "
                    "Set ALLOW_DEMO_SEED=true to force."
                )
            )
            return
        # Tracks
        python_track, _ = Track.objects.get_or_create(
            slug="python-path",
            defaults={
                "title": "Python Path",
                "title_ru": "Путь Python",
                "description": "Learn Python fundamentals through guided worlds.",
                "description_ru": "Освой основы Python через серию миров и миссий.",
                "tagline_en": "Your first quest chain",
                "tagline_ru": "Твоя первая цепочка квестов",
                "color_theme": "from-indigo-900/60 via-primary/20 to-sky-500/20",
            },
        )

        # Locations
        world1, _ = Location.objects.get_or_create(
            title="World 1",
            defaults={
                "track": python_track,
                "order": 1,
                "title_en": "World 1",
                "title_ru": "Мир 1: Основы Python",
                "description_en": "Core islands that introduce Python syntax and flow.",
                "description_ru": "Архипелаг с базовыми уроками по синтаксису и логике Python.",
            },
        )
        if world1.track_id is None:
            world1.track = python_track
            world1.save(update_fields=["track"])
        world2, _ = Location.objects.get_or_create(
            title="World 2",
            defaults={
                "track": python_track,
                "order": 2,
                "title_en": "World 2",
                "title_ru": "Мир 2: Врата Django",
                "description_en": "Transition world that prepares students for backend quests.",
                "description_ru": "Переходный мир с подготовкой к заданиям Django и бэкенду.",
            },
        )
        if world2.track_id is None:
            world2.track = python_track
            world2.save(update_fields=["track"])

        # Missions
        intro, _ = Mission.objects.get_or_create(
            title="Intro",
            defaults={
                "location": world1,
                "order": 1,
                "is_active": True,
                "min_level": 1,
                "xp_reward": 100,
                "repeatable": True,
                "repeat_xp_rate": 10,
                "pos_x": 12,
                "pos_y": 72,
                "title_en": "Intro",
                "title_ru": "Интродукция",
                "description_en": "Learn the interface, energy system and first Python spell.",
                "description_ru": "Знакомство с интерфейсом, энергией и первой Python-функцией.",
            },
        )

        gate, _ = Mission.objects.get_or_create(
            title="Gate",
            defaults={
                "location": world1,
                "order": 2,
                "is_active": True,
                "min_level": 2,
                "xp_reward": 120,
                "repeatable": False,
                "repeat_xp_rate": 0,
                "pos_x": 37,
                "pos_y": 52,
                "title_en": "Gate",
                "title_ru": "Врата",
                "description_en": "Boss checkpoint that verifies loops and conditions.",
                "description_ru": "Босс-проверка на циклы и условия перед следующим миром.",
            },
        )

        repeatable, _ = Mission.objects.get_or_create(
            title="Repeatable",
            defaults={
                "location": world2,
                "order": 1,
                "is_active": True,
                "min_level": 1,
                "xp_reward": 50,
                "repeatable": True,
                "repeat_xp_rate": 20,
                "pos_x": 62,
                "pos_y": 37,
                "title_en": "Repeatable",
                "title_ru": "Повторяемая миссия",
                "description_en": "Optional skirmish for extra XP and practicing snippets.",
                "description_ru": "Дополнительный бой для прокачки XP и отработки сниппетов.",
            },
        )

        # Prerequisite: Gate requires Intro
        gate.prerequisites.add(intro)

        self.stdout.write(self.style.SUCCESS("Demo content loaded."))
