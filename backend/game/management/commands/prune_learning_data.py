"""Delete old behavioural footprint (retention limit).

    python manage.py prune_learning_data              # LEARNING_DATA_RETENTION_DAYS
    python manage.py prune_learning_data --days 365 --dry-run

Removes code runs and timeline events older than the limit. Progress counters
(TaskProgress, Progress) are the learner's course state and are kept. Run it
from a scheduler (for example a weekly Railway cron job).
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.models import CodeRun, LearningEvent


class Command(BaseCommand):
    help = "Delete code runs and learning events older than the retention limit."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Keep this many days (default: LEARNING_DATA_RETENTION_DAYS).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Only count.")

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = getattr(settings, "LEARNING_DATA_RETENTION_DAYS", 730)
        if days < 1:
            raise CommandError("--days must be at least 1")

        cutoff = timezone.now() - timedelta(days=days)
        runs = CodeRun.objects.filter(created_at__lt=cutoff)
        events = LearningEvent.objects.filter(created_at__lt=cutoff)
        n_runs, n_events = runs.count(), events.count()
        if not options["dry_run"]:
            runs.delete()
            events.delete()
        verb = "would delete" if options["dry_run"] else "deleted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {n_runs} code run(s) and {n_events} event(s) "
                f"older than {days} days"
            )
        )
