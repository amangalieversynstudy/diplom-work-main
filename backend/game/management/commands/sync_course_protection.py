"""Bring the protection of the built-in code steps to a database that is already running.

The protection is the "not taught yet" lists, the personal variants and the "explain your solution"
question that follows a personalised code step (a quiz marked ``data.kind = "explain"``).

``seed_course`` only loads what is missing, and ``seed_course --force`` reloads the whole course and with
it every edit a teacher made. The "not taught yet" lists (``data.not_yet``) and the personal variants
(``data.variants``) were added to the fixtures later, so a live database does not have them. This command
copies just those steps from the fixtures:

    python manage.py sync_course_protection --dry-run   # what would change
    python manage.py sync_course_protection             # steps that do not have the protection yet
    python manage.py sync_course_protection --force     # also steps that already have it

A step is copied whole (titles, text and data), because variants only work together with their
placeholders in the text, the starter and the hidden check. Order, rewards and progress are not touched.
Explain questions that are missing are created, with the ids the fixtures give them (only when their
mission exists); one whose data differs from the fixture is brought in line, because its variants have to
match the code step's variants (the question must use the learner's own numbers). Only steps of the built-in fixtures are considered.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from game.models import Mission, MissionTask

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURES = ("intro_course.json", "python_continued.json")
PROTECTION_KEYS = ("not_yet", "variants")
TEXT_FIELDS = ("title", "title_en", "title_ru", "body", "body_en", "body_ru")


def protected_steps():
    """{pk: fields} of the fixture's code steps that carry ``not_yet`` or ``variants``."""
    steps = {}
    for name in FIXTURES:
        for row in json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")):
            if row["model"] != "game.missiontask":
                continue
            fields = row["fields"]
            data = fields.get("data", {})
            if fields.get("task_type") == "code" and any(key in data for key in PROTECTION_KEYS):
                steps[row["pk"]] = fields
    return steps


def explain_steps():
    """{pk: fields} of the fixture's "explain your solution" questions."""
    steps = {}
    for name in FIXTURES:
        for row in json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")):
            fields = row["fields"] if row["model"] == "game.missiontask" else {}
            if fields.get("data", {}).get("kind") == "explain":
                steps[row["pk"]] = fields
    return steps


class Command(BaseCommand):
    help = "Copy 'not taught yet' lists and personal variants of the built-in steps into a live database."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only say what would change.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Also overwrite steps that already have not_yet or variants.",
        )

    def handle(self, *args, **options):
        dry, force = options["dry_run"], options["force"]
        changed = 0
        for pk, fields in sorted(protected_steps().items()):
            task = MissionTask.objects.filter(pk=pk).first()
            if task is None:
                self.stdout.write(f"step {pk}: not in this database, skipped")
                continue
            current = task.data if isinstance(task.data, dict) else {}
            if not force and any(key in current for key in PROTECTION_KEYS):
                self.stdout.write(f"step {pk}: already protected, skipped (use --force)")
                continue
            same_text = all(getattr(task, f) == fields[f] for f in TEXT_FIELDS if f in fields)
            if current == fields["data"] and same_text:
                self.stdout.write(f"step {pk}: up to date")
                continue
            self.stdout.write(f"step {pk}: {'would update' if dry else 'updated'}")
            changed += 1
            if dry:
                continue
            for field in TEXT_FIELDS:
                if field in fields:
                    setattr(task, field, fields[field])
            task.data = fields["data"]
            task.save(update_fields=[*(f for f in TEXT_FIELDS if f in fields), "data"])
        for pk, fields in sorted(explain_steps().items()):
            task = MissionTask.objects.filter(pk=pk).first()
            if task is None:
                mission_id = fields["mission"]
                if not Mission.objects.filter(pk=mission_id).exists():
                    self.stdout.write(f"explain step {pk}: its mission is not in this database, skipped")
                    continue
                self.stdout.write(f"explain step {pk}: {'would create' if dry else 'created'}")
                changed += 1
                if not dry:
                    values = {k: v for k, v in fields.items() if k != "mission"}
                    MissionTask.objects.create(pk=pk, mission_id=mission_id, **values)
            elif task.data != fields["data"]:  # explain steps belong to the fixture: keep their variants in line with the code step
                self.stdout.write(f"explain step {pk}: {'would update' if dry else 'updated'}")
                changed += 1
                if not dry:
                    task.data = fields["data"]
                    for field in TEXT_FIELDS:
                        if field in fields:
                            setattr(task, field, fields[field])
                    task.save()
            else:
                self.stdout.write(f"explain step {pk}: present")
        verb = "would change" if dry else "changed"
        self.stdout.write(self.style.SUCCESS(f"{verb} {changed} step(s)"))
