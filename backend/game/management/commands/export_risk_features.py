"""Export learner snapshots for training the drop-out risk model.

    python manage.py export_risk_features --out risk_features.csv
    (cd ml && python -m risk.train --features ../risk_features.csv --out ../risk_model)

A snapshot is taken every ``--step-days`` after a learner's first ``--window-days``
of activity. Its features describe the window that just ended; its label says
whether the learner then stayed silent for the next ``--horizon-days``. Left out:

* snapshots whose horizon has not fully passed yet (the outcome is unknown);
* snapshots where the learner had no unfinished mission (finishing the course is
  not dropping out);
* snapshots with no activity in the window, and everything after a learner's
  first drop-out: "silent, then still silent" is trivially true and would only
  teach the model that inactive people are inactive.

Same privacy rules as ``export_learning_data``: only learners with research
consent unless ``--all-users``, staff never, ids replaced by a keyed hash.
"""

import csv
from bisect import bisect_left
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.management.commands.export_learning_data import pseudonym
from game.models import Progress
from game.risk import BASE_FEATURES, activity_rows, features_from
from users.models import Profile

GROUP, PERIOD, LABEL = "learner", "period", "label"


def has_open_mission(intervals, moment):
    """Was any mission started but not yet completed at ``moment``?"""
    return any(
        start <= moment and (end is None or end > moment) for start, end in intervals
    )


def snapshots(rows, intervals, *, window, horizon, step, now):
    """Yield ``(anchor, features, label)`` for one learner's activity ``rows``.

    The series ends at the learner's first drop-out.
    """
    if not rows:
        return
    stamps = sorted(row[0] for row in rows)
    anchor = stamps[0] + window
    while anchor + horizon <= now:
        if has_open_mission(intervals, anchor):
            features = features_from(rows, anchor, window.days)
            if features["events"]:
                index = bisect_left(stamps, anchor)
                silent = index >= len(stamps) or stamps[index] >= anchor + horizon
                yield anchor, features, int(silent)
                if silent:
                    return
        anchor += step


class Command(BaseCommand):
    help = "Export windowed activity snapshots with a drop-out label (CSV)."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="Output CSV file.")
        parser.add_argument("--window-days", type=int, default=14)
        parser.add_argument("--horizon-days", type=int, default=14)
        parser.add_argument("--step-days", type=int, default=7)
        parser.add_argument("--all-users", action="store_true")

    def handle(self, *args, **options):
        window_days, horizon_days, step_days = (
            options["window_days"], options["horizon_days"], options["step_days"],
        )
        if min(window_days, horizon_days, step_days) < 1:
            raise CommandError("window, horizon and step must be at least one day")
        window, horizon, step = (
            timedelta(days=window_days), timedelta(days=horizon_days), timedelta(days=step_days),
        )
        key = getattr(settings, "ANALYTICS_EXPORT_SALT", "") or settings.SECRET_KEY
        now = timezone.now()

        learners = Profile.objects.filter(user__is_staff=False)
        if not options["all_users"]:
            learners = learners.filter(research_consent=True)
        ids = list(learners.values_list("user_id", flat=True))

        rows = activity_rows(ids)
        intervals = {user_id: [] for user_id in ids}
        started = Progress.objects.filter(
            user_id__in=ids, started_at__isnull=False
        ).values_list("user_id", "started_at", "completed_at")
        for user_id, start, end in started:
            intervals[user_id].append((start, end))

        written = positives = 0
        path = Path(options["out"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([GROUP, PERIOD, *BASE_FEATURES, LABEL])
            for user_id in ids:
                for anchor, features, label in snapshots(
                    rows[user_id], intervals[user_id],
                    window=window, horizon=horizon, step=step, now=now,
                ):
                    writer.writerow(
                        [pseudonym(user_id, key), anchor.date().isoformat()]
                        + [features[name] for name in BASE_FEATURES]
                        + [label]
                    )
                    written += 1
                    positives += label
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {written} snapshot(s) ({positives} drop-outs) from "
                f"{len(ids)} learner(s) to {path.resolve()}"
            )
        )
