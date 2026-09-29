"""Export the behavioural footprint as CSV files for analysis.

    python manage.py export_learning_data --out analytics_export

Privacy by construction:
  * only learners who gave research consent are exported (``--all-users`` for
    internal, non-published analysis); teachers/staff are never exported;
  * user ids are replaced by a keyed hash (set ANALYTICS_EXPORT_SALT; it falls
    back to SECRET_KEY) - no username, e-mail or display name is written;
  * the learner's code and the tasks' answer keys are never exported, only
    measurements (sizes, exit codes, error classes, counters).
"""

import csv
import hashlib
import hmac
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from game.models import CodeRun, LearningEvent, MissionTask, Progress, TaskProgress
from users.models import Profile


def pseudonym(user_id, key):
    """Stable, non-reversible id for a user (same key -> same id across exports)."""
    digest = hmac.new(key.encode(), f"user:{user_id}".encode(), hashlib.sha256)
    return digest.hexdigest()[:16]


class Command(BaseCommand):
    help = "Export anonymised learning data (runs, events, progress) to CSV."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="analytics_export", help="Output directory.")
        parser.add_argument(
            "--all-users",
            action="store_true",
            help="Include learners without research consent (internal use only).",
        )

    def handle(self, *args, **options):
        key = getattr(settings, "ANALYTICS_EXPORT_SALT", "") or settings.SECRET_KEY
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)

        learners = Profile.objects.filter(user__is_staff=False)
        if not options["all_users"]:
            learners = learners.filter(research_consent=True)
        ids = set(learners.values_list("user_id", flat=True))

        def who(user_id):
            return pseudonym(user_id, key)

        self._write(
            out / "users.csv",
            ["user", "level", "xp", "longest_streak", "consent_at"],
            (
                [who(p.user_id), p.level, p.xp, p.longest_streak, p.research_consent_at]
                for p in learners.iterator()
            ),
        )
        self._write(
            out / "tasks.csv",
            ["task", "mission", "task_type", "order", "is_required"],
            (
                [t.id, t.mission_id, t.task_type, t.order, t.is_required]
                for t in MissionTask.objects.all().iterator()
            ),
        )
        self._write(
            out / "runs.csv",
            [
                "user", "task", "outcome", "error_type", "error_message", "exit_code",
                "duration_ms", "code_length", "stdout_size", "stderr_size", "passed",
                "attempt_no", "after_solved", "created_at",
            ],
            (
                [
                    who(r.user_id), r.task_id, r.outcome, r.error_type, r.error_message,
                    r.exit_code, r.duration_ms, r.code_length, r.stdout_size,
                    r.stderr_size, r.passed, r.attempt_no, r.after_solved, r.created_at,
                ]
                for r in CodeRun.objects.filter(user_id__in=ids)
                .order_by("created_at")
                .iterator()
            ),
        )
        self._write(
            out / "events.csv",
            ["user", "event_type", "task", "mission", "meta", "created_at"],
            (
                [
                    who(e.user_id), e.event_type, e.task_id, e.mission_id,
                    json.dumps(e.meta, ensure_ascii=False, sort_keys=True), e.created_at,
                ]
                for e in LearningEvent.objects.filter(user_id__in=ids)
                .order_by("created_at")
                .iterator()
            ),
        )
        self._write(
            out / "task_progress.csv",
            ["user", "task", "status", "attempts", "best_score", "last_submitted_at"],
            (
                [
                    who(t.user_id), t.task_id, t.status, t.attempts, t.best_score,
                    t.last_submitted_at,
                ]
                for t in TaskProgress.objects.filter(user_id__in=ids).iterator()
            ),
        )
        self._write(
            out / "mission_progress.csv",
            [
                "user", "mission", "status", "completed", "attempts", "stars",
                "xp_earned", "started_at", "completed_at",
            ],
            (
                [
                    who(p.user_id), p.mission_id, p.status, p.completed, p.attempts,
                    p.stars, p.xp_earned, p.started_at, p.completed_at,
                ]
                for p in Progress.objects.filter(user_id__in=ids).iterator()
            ),
        )
        self.stdout.write(
            self.style.SUCCESS(f"Exported {len(ids)} learner(s) to {out.resolve()}")
        )

    @staticmethod
    def _write(path, header, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
