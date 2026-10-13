"""Write today's early-warning list to the database (the data behind hypothesis H3).

    python manage.py snapshot_early_warning

Run it once a day: the in-process scheduler (``ENABLE_STREAK_SCHEDULER=1``) does it, and the same command can
run as a Railway cron job (``0 4 * * *``). Safe to repeat: one snapshot per UTC date, a second run does
nothing. Only learners who agreed to the research are written; a row holds the level, the score and the
reason codes, nothing else.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from game.snapshots import take_snapshot


class Command(BaseCommand):
    help = "Store today's early-warning list (consenting learners only), once per day."

    def handle(self, *args, **options):
        created = take_snapshot()
        today = timezone.now().date()
        if created:
            self.stdout.write(self.style.SUCCESS(f"snapshot {today}: {created} learner(s)"))
        else:
            self.stdout.write(f"snapshot {today}: nothing to do (already taken or nobody to write)")
