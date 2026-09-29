"""Write the weekly pilot report.

    python manage.py pilot_report --out pilot_report.md
    python manage.py pilot_report --json          # print the raw numbers

Only counts and rates are written; no names, addresses or code.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from game.pilot import build_report, render_markdown


class Command(BaseCommand):
    help = "Summarise the pilot: participants, KPIs, the help experiment, sandbox health."

    def add_arguments(self, parser):
        parser.add_argument("--out", help="Markdown file to write (default: print).")
        parser.add_argument("--json", action="store_true", help="Print the raw numbers as JSON.")

    def handle(self, *args, **options):
        report = build_report()
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
