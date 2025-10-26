"""Management command to seed demo locations and missions.

This command is intended for local/dev environments to quickly populate
the database with two locations and three missions (including a repeatable
one) for manual testing. In non-debug environments it requires the
environment variable ALLOW_DEMO_SEED=true to proceed.
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from game.models import Location, Mission


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
        # Locations
        world1, _ = Location.objects.get_or_create(
            title="World 1", defaults={"order": 1}
        )
        world2, _ = Location.objects.get_or_create(
            title="World 2", defaults={"order": 2}
        )

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
            },
        )

        # Prerequisite: Gate requires Intro
        gate.prerequisites.add(intro)

        self.stdout.write(self.style.SUCCESS("Demo content loaded."))
