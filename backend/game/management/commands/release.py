"""Everything a deploy runs before the server starts, in ONE Python process.

Each separate ``manage.py`` call boots Django again: seconds of CPU on a small Railway instance, on every deploy
and every restart. Steps, all idempotent: migrations, the superuser from DJANGO_SUPERUSER_* (if set), the
built-in courses, their variants and explain steps. An error stops the start (no ``|| true``): a half-migrated
database must not serve. Static files are collected when the image is built (Dockerfile.backend).
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

STEPS = (
    ("migrate", {"interactive": False}),
    ("ensure_superuser", {}),
    ("seed_course", {}),
    ("sync_course_protection", {}),
)


class Command(BaseCommand):
    help = "Prepare the database for this deploy: migrations, superuser, built-in courses."

    def handle(self, *args, **options):
        for name, kwargs in STEPS:
            self.stdout.write(f"[release] {name}")
            call_command(name, **kwargs)
        self.stdout.write("[release] done")
