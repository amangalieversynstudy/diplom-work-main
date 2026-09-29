"""Seed the built-in fixtures (ranks, class roles, intro course) safely.

A bare ``loaddata`` overwrites rows by primary key every time it runs, so using
it in the deploy start command silently reverted anything a course author had
edited in the admin or Studio. This command only loads what is missing:

    python manage.py seed_course           # first deploy / empty database
    python manage.py seed_course --force   # deliberately reload from fixtures

``--force`` overwrites the fixture rows (same primary keys) and therefore any
manual edits to them - use it only to publish a new version of the built-in
course.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from game.models import ClassRole, Rank, Track

INTRO_TRACK_SLUG = "python-intro"

# fixture name -> (human label, "is it already there?" check)
FIXTURES = (
    ("ranks", "ranks", lambda: Rank.objects.exists()),
    ("class_roles", "class roles", lambda: ClassRole.objects.exists()),
    (
        "intro_course",
        "intro course",
        lambda: Track.objects.filter(slug=INTRO_TRACK_SLUG).exists(),
    ),
)


class Command(BaseCommand):
    help = "Load ranks, class roles and the intro course if they are missing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reload every fixture even if it exists (overwrites manual edits).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        for fixture, label, already_loaded in FIXTURES:
            if already_loaded() and not force:
                self.stdout.write(
                    f"skip {label}: already present (use --force to overwrite)"
                )
                continue
            call_command("loaddata", fixture, verbosity=0)
            self.stdout.write(self.style.SUCCESS(f"loaded {label}"))
