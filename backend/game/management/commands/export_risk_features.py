"""Export learner snapshots for training the drop-out risk model.

    cd backend
    python manage.py export_risk_features --include-performance --out ../risk_features.csv \\
        --performance-out ../performance.csv
    (cd ../ml && python -m risk.train --features ../risk_features.csv --performance ../performance.csv --out ../risk_model)

A snapshot is taken every ``--step-days`` after a learner's first ``--window-days``
of activity. Its features describe the window that just ended; its label says
whether the learner then stayed silent for the next ``--horizon-days``. Left out:

* snapshots whose horizon has not fully passed yet (the outcome is unknown), or runs past ``--until``
  (default ``PILOT_ENDED_AT``): after the course everybody goes quiet, and that is not dropping out;
* snapshots where the learner was not inside a started, unfinished pilot course (``cohort.in_course``):
  finishing the course is not dropping out, a learner between two missions still counts;
* snapshots with no activity in the window, and everything after a learner's
  first drop-out: "silent, then still silent" is trivially true and would only
  teach the model that inactive people are inactive.

Each row also carries the rule-based early-warning level and score from the last daily snapshot taken before
the row's anchor (``rule_level``, ``rule_score``; empty when there is none within two days), so the model can be
compared with the rules on the same rows.

``--performance-out`` writes a second table, one row per learner: the features of the learner's first window and
the composite 50/30/20 score at the end of the period (pilot content only), for the score forecast.

Same privacy rules as ``export_learning_data``: only research participants (``cohort.research_learners``)
unless ``--all-users``, staff and teachers never, ids replaced by a keyed hash.
"""

import csv
from bisect import bisect_left
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.cohort import course_spans, in_course, parse_moment, pilot_period, research_learners
from game.management.commands.export_learning_data import pseudonym
from game.metrics import ABANDON_WINDOW_DAYS, student_performance_map
from game.models import EarlyWarningSnapshot
from game.risk import BASE_FEATURES, activity_rows, features_from

GROUP, PERIOD, LABEL = "learner", "period", "label"
RULE_LEVEL, RULE_SCORE = "rule_level", "rule_score"
RULE_MAX_AGE_DAYS = 2  # an older snapshot is no longer the rules' view at the anchor
PILOT_ONLY = SimpleNamespace(is_superuser=True, pilot_only=True)


def snapshots(rows, spans, *, window, horizon, step, now):
    """Yield ``(anchor, features, label)`` for one learner's activity ``rows``.

    ``spans`` are the learner's pilot courses (``cohort.course_spans``). The series ends at the first drop-out.
    """
    if not rows:
        return
    stamps = sorted(row[0] for row in rows)
    anchor = stamps[0] + window
    while anchor + horizon <= now:
        if in_course(spans, anchor):
            features = features_from(rows, anchor, window.days)
            if features["events"]:
                index = bisect_left(stamps, anchor)
                silent = index >= len(stamps) or stamps[index] >= anchor + horizon
                yield anchor, features, int(silent)
                if silent:
                    return
        anchor += step


def rule_at(history, anchor):
    """``(level, score)`` of the last snapshot strictly before the anchor's day, at most two days old."""
    if not history:
        return "", ""
    days = [day for day, _, _ in history]
    index = bisect_left(days, anchor.date()) - 1
    if index < 0 or days[index] < anchor.date() - timedelta(days=RULE_MAX_AGE_DAYS):
        return "", ""
    _, level, score = history[index]
    return level, score


def parse_until(value):
    """``--until`` as an aware datetime: an ISO date-time with a zone, or a date (its UTC midnight)."""
    moment = parse_moment(value)
    if moment is not None:
        return moment
    try:
        return datetime.combine(date.fromisoformat(str(value).strip()), time.min, tzinfo=dt_timezone.utc)
    except ValueError as error:
        raise CommandError(f"--until: ожидается дата или дата-время с часовым поясом, получено {value!r}") from error


class Command(BaseCommand):
    help = "Export windowed activity snapshots with a drop-out label (CSV)."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="Output CSV file.")
        parser.add_argument("--window-days", type=int, default=14)
        parser.add_argument("--horizon-days", type=int, default=ABANDON_WINDOW_DAYS)  # the one definition of "left"
        parser.add_argument("--step-days", type=int, default=7)
        parser.add_argument(
            "--until",
            help="End of the observed period (ISO date or date-time with a zone); default PILOT_ENDED_AT, else now.",
        )
        parser.add_argument("--all-users", action="store_true")
        parser.add_argument(
            "--include-performance",
            action="store_true",
            help="Append the learner's 50/30/20 composite performance_score column.",
        )
        parser.add_argument(
            "--performance-out",
            help="Also write one row per learner: first-window features and the score at the end of the period.",
        )

    def handle(self, *args, **options):
        window_days, horizon_days, step_days = (
            options["window_days"], options["horizon_days"], options["step_days"],
        )
        if min(window_days, horizon_days, step_days) < 1:
            raise CommandError("window, horizon and step must be at least one day")
        window, horizon, step = (
            timedelta(days=window_days), timedelta(days=horizon_days), timedelta(days=step_days),
        )
        if not getattr(settings, "ANALYTICS_EXPORT_SALT", ""):
            self.stderr.write(
                "ANALYTICS_EXPORT_SALT is empty: pseudonyms fall back to SECRET_KEY and will not match exports made "
                "with the salt. Copy the value from the server variables before exporting research data."
            )
        key = getattr(settings, "ANALYTICS_EXPORT_SALT", "") or settings.SECRET_KEY
        now = timezone.now()
        until = parse_until(options["until"]) if options.get("until") else pilot_period()[1]
        stop = min(now, until) if until is not None else now

        if options["all_users"]:
            learners = get_user_model().objects.filter(is_staff=False, is_teacher=False)
        else:
            learners = research_learners()
        ids = list(learners.values_list("pk", flat=True))

        rows = activity_rows(ids)
        spans = course_spans(ids)
        history = {user_id: [] for user_id in ids}
        for user_id, day, level, score in (
            EarlyWarningSnapshot.objects.filter(user_id__in=ids)
            .order_by("date")
            .values_list("user_id", "date", "level", "score")
        ):
            history[user_id].append((day, level, score))

        include_perf = bool(options.get("include_performance"))
        perf_map = (
            student_performance_map(PILOT_ONLY, ids, until=stop)
            if include_perf or options.get("performance_out") else {}
        )

        written = positives = 0
        path = Path(options["out"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            header = [GROUP, PERIOD, *BASE_FEATURES, LABEL, RULE_LEVEL, RULE_SCORE]
            if include_perf:
                header.append("performance_score")
            writer.writerow(header)
            for user_id in ids:
                for anchor, features, label in snapshots(
                    rows[user_id], spans.get(user_id, []),
                    window=window, horizon=horizon, step=step, now=stop,
                ):
                    writer.writerow(
                        [pseudonym(user_id, key), anchor.date().isoformat()]
                        + [features[name] for name in BASE_FEATURES]
                        + [label, *rule_at(history[user_id], anchor)]
                        + ([(perf_map.get(user_id) or {}).get("score") or 0.0] if include_perf else [])
                    )
                    written += 1
                    positives += label
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {written} snapshot(s) ({positives} drop-outs) from "
                f"{len(ids)} learner(s) to {path.resolve()}"
            )
        )
        if options.get("performance_out"):
            self._write_performance(Path(options["performance_out"]), ids, rows, perf_map, window, stop, key)

    def _write_performance(self, path, ids, rows, perf_map, window, stop, key):
        """One row per learner whose first window is over by ``stop``: its features and the final score."""
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([GROUP, "first_day", *BASE_FEATURES, "performance_score"])
            for user_id in ids:
                if not rows[user_id]:
                    continue
                first = min(row[0] for row in rows[user_id])
                anchor = first + window
                if anchor > stop:
                    continue  # the first window is not over: no forecast to check yet
                score = (perf_map.get(user_id) or {}).get("score")
                if score is None:
                    continue
                features = features_from(rows[user_id], anchor, window.days)
                writer.writerow(
                    [pseudonym(user_id, key), first.date().isoformat()]
                    + [features[name] for name in BASE_FEATURES]
                    + [score]
                )
                written += 1
        self.stdout.write(self.style.SUCCESS(f"Wrote {written} learner(s) with a final score to {path.resolve()}"))
