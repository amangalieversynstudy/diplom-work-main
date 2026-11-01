"""Write the weekly pilot report.

    python manage.py pilot_report --out pilot_report.md
    python manage.py pilot_report --json          # print the raw numbers
    python manage.py pilot_report --contacts contacts.csv   # H3 also without the days after a teacher's contact

The contact log is the teacher's own CSV with a header ``username,date`` (date as YYYY-MM-DD): one row per
contact with a learner on the "urgent" or "attention" list. Only the first date of each learner is used.

Only counts and rates are written; no names, addresses or code.
"""

import csv
import json
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from game.pilot import build_report, render_markdown


def read_contacts(path):
    """``{user_id: first contact date}`` from the teacher's contact log; unknown logins are reported, not fatal."""
    first, unknown = {}, []
    users = dict(get_user_model().objects.values_list("username", "pk"))
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("username") or "").strip()
                try:
                    day = date.fromisoformat((row.get("date") or "").strip()[:10])
                except ValueError as error:
                    raise CommandError(f"{path}: неверная дата у {name!r}: {row.get('date')!r}") from error
                if name not in users:
                    unknown.append(name)
                    continue
                user_id = users[name]
                if user_id not in first or day < first[user_id]:
                    first[user_id] = day
    except OSError as error:
        raise CommandError(f"Не удалось прочитать журнал контактов: {error}") from error
    return first, unknown


class Command(BaseCommand):
    help = "Summarise the pilot: participants, KPIs, the help experiment, H3, sandbox health."

    def add_arguments(self, parser):
        parser.add_argument("--out", help="Markdown file to write (default: print).")
        parser.add_argument("--json", action="store_true", help="Print the raw numbers as JSON.")
        parser.add_argument("--contacts", help="Teacher's contact log, CSV with username,date.")

    def handle(self, *args, **options):
        contacts = None
        if options.get("contacts"):
            contacts, unknown = read_contacts(options["contacts"])
            if unknown:
                self.stderr.write(f"В журнале контактов неизвестные логины (пропущены): {', '.join(sorted(set(unknown)))}")
        report = build_report(contacts=contacts)
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            return
        text = render_markdown(report)
        if options["out"]:
            path = Path(options["out"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Report written to {path.resolve()}"))
        else:
            self.stdout.write(text)
