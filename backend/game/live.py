"""The teacher's live picture: who is working right now, and how stale that picture is.

The panel asks for fresh data every ``POLL_SECONDS`` seconds. Nothing is cached or pre-aggregated: the answer
is computed from the event tables at the moment of the request, so the only delay between a learner's action
and the panel is the polling interval plus the request itself.

That delay is the parameter "data freshness". It is measured, not assumed: with each request the panel says
when its previous answer was generated (``since``), and the learner actions that appeared in between get a lag
(the moment the panel received them minus the moment the learner did them). One :class:`FreshnessSample` is
written per request that carried new actions; ``freshness_summary`` and the pilot report read them back.

Only numbers about activity are kept. What the feed shows (a learner's name, a step's title, what happened)
is limited to the viewer's own learners and the viewer's own courses, like the rest of the teacher's screens.
"""

from datetime import timedelta

from django.db.models import Max, Q
from django.utils import timezone

from .models import CodeRun, FreshnessSample, LearningEvent
from .classes import TASK_TRACK, visible_events, visible_work
from .warning import scoped_learners

POLL_SECONDS = 10
ACTIVE_WINDOW = timedelta(minutes=5)
FEED_SIZE = 10
FEED_LOOKBACK = timedelta(hours=2)
# a panel that was silent for longer (hidden tab, sleeping laptop) does not know what it had shown: no sample
MAX_GAP = timedelta(seconds=3 * POLL_SECONDS)
FRESHNESS_TARGET_S = 15  # the panel is "fresh" when every new action reached it within this many seconds
SAMPLE_CAP = 500  # actions per request taken into one sample

# LearningEvent types that say something a teacher wants to see as it happens
_EVENT_KIND = {
    LearningEvent.MISSION_STARTED: "mission_started",
    LearningEvent.MISSION_COMPLETED: "mission_completed",
    LearningEvent.HELP_OFFERED: "help_offered",
    LearningEvent.HINT_USED: "hint",
    LearningEvent.SKELETON_USED: "skeleton",
    LearningEvent.AI_HINT_USED: "mentor",
    LearningEvent.AI_MENTOR_USED: "mentor",
    LearningEvent.TASK_SUBMITTED: "answer",
}


def _own_events(viewer):
    # the viewer's courses, a closed one only while the learner is enrolled; Q() for a superuser
    return visible_events(viewer)


def _own_runs(viewer):
    return visible_work(viewer, TASK_TRACK)


def _title(obj, lang):
    if obj is None:
        return ""
    return obj.get_localized_title(lang) or f"#{obj.pk}"


def _event_item(event, lang):
    kind = _EVENT_KIND[event.event_type]
    meta = event.meta if isinstance(event.meta, dict) else {}
    if kind == "answer":
        if meta.get("after_solved"):
            return None  # the learner repeats a solved step: nothing new
        prefix = "explain" if meta.get("kind") == "explain" else "quiz"
        kind = f"{prefix}_{'ok' if meta.get('correct') else 'fail'}"
    obj = event.task or event.mission
    return {
        "kind": kind,
        "learner": event.user.username,
        "learner_id": event.user_id,
        "title": _title(obj, lang),
        "at": event.created_at,
    }


def _run_item(run, lang):
    if run.after_solved:
        return None
    kind = "code_run" if run.passed is None else ("code_ok" if run.passed else "code_fail")
    return {
        "kind": kind,
        "learner": run.user.username,
        "learner_id": run.user_id,
        "title": _title(run.task, lang),
        "at": run.created_at,
    }


def live_feed(viewer, *, lang="ru", now=None):
    """The latest things the viewer's learners did in the viewer's courses, newest first."""
    now = now or timezone.now()
    since = now - FEED_LOOKBACK
    learners = scoped_learners(viewer)
    events = (
        LearningEvent.objects.filter(user__in=learners, created_at__gte=since, event_type__in=list(_EVENT_KIND))
        .filter(_own_events(viewer))
        .select_related("user", "task", "mission")
        .order_by("-created_at")[: FEED_SIZE * 2]
    )
    runs = (
        CodeRun.objects.filter(user__in=learners, created_at__gte=since)
        .exclude(outcome="runner_error")
        .filter(_own_runs(viewer))
        .select_related("user", "task")
        .order_by("-created_at")[: FEED_SIZE * 2]
    )
    items = [item for item in (*(_event_item(e, lang) for e in events), *(_run_item(r, lang) for r in runs)) if item]
    items.sort(key=lambda item: item["at"], reverse=True)
    items = items[:FEED_SIZE]
    for item in items:
        item["lag_s"] = max(0, round((now - item["at"]).total_seconds()))
    return items


def _activity_stamps(learners, *, viewer=None, after=None, until=None):
    events = LearningEvent.objects.filter(user__in=learners)
    runs = CodeRun.objects.filter(user__in=learners)
    if viewer is not None:
        # only what happened in the viewer's own courses (runs without a step belong to none)
        events, runs = events.filter(_own_events(viewer)), runs.filter(_own_runs(viewer))
    if after is not None:
        events, runs = events.filter(created_at__gt=after), runs.filter(created_at__gt=after)
    if until is not None:
        events, runs = events.filter(created_at__lte=until), runs.filter(created_at__lte=until)
    return events, runs


def _record_freshness(viewer, learners, since, now):
    """One sample for the actions that happened since the panel's previous answer (see the module doc)."""
    if since is None or not (timedelta(0) < now - since <= MAX_GAP):
        return
    events, runs = _activity_stamps(learners, viewer=viewer, after=since, until=now)
    stamps = list(events.values_list("created_at", flat=True)[:SAMPLE_CAP])
    stamps += list(runs.values_list("created_at", flat=True)[:SAMPLE_CAP])
    if not stamps:
        return
    lags = [max(0.0, (now - stamp).total_seconds()) for stamp in stamps]
    FreshnessSample.objects.create(
        viewer=viewer,
        polled_at=now,
        new_events=len(lags),
        lag_mean_s=round(sum(lags) / len(lags), 3),
        lag_max_s=round(max(lags), 3),
    )


def freshness_summary(*, viewer=None, since=None):
    """How stale the panel was: {samples, events, mean_s, worst_s, within_target_pct, target_s}.

    ``mean_s`` is per action; ``within_target_pct`` is the share of measurements in which even the
    slowest action arrived within FRESHNESS_TARGET_S. Without measurements the numbers are None.
    """
    samples = FreshnessSample.objects.all()
    if viewer is not None:
        samples = samples.filter(viewer=viewer)
    if since is not None:
        samples = samples.filter(polled_at__gte=since)
    rows = list(samples.values_list("new_events", "lag_mean_s", "lag_max_s"))
    summary = {"samples": len(rows), "events": 0, "mean_s": None, "worst_s": None,
               "within_target_pct": None, "target_s": FRESHNESS_TARGET_S}
    if not rows:
        return summary
    events = sum(n for n, _, _ in rows)
    summary.update(
        events=events,
        mean_s=round(sum(n * mean for n, mean, _ in rows) / events, 1),
        worst_s=round(max(worst for _, _, worst in rows), 1),
        within_target_pct=round(100 * sum(1 for _, _, worst in rows if worst <= FRESHNESS_TARGET_S) / len(rows)),
    )
    return summary


def live_panel(viewer, *, lang="ru", since=None, now=None):
    """Everything the teacher's live card shows, and the measurement of how stale the previous one was."""
    now = now or timezone.now()
    learners = scoped_learners(viewer)
    _record_freshness(viewer, learners, since, now)

    window = now - ACTIVE_WINDOW
    events, runs = _activity_stamps(learners, viewer=viewer)
    active = set(events.filter(created_at__gte=window).values_list("user_id", flat=True))
    active |= set(runs.filter(created_at__gte=window).values_list("user_id", flat=True))
    latest = [
        stamp
        for stamp in (
            events.aggregate(last=Max("created_at"))["last"],
            runs.aggregate(last=Max("created_at"))["last"],
        )
        if stamp
    ]
    return {
        "generated_at": now.isoformat(),
        "poll_seconds": POLL_SECONDS,
        "active_window_minutes": int(ACTIVE_WINDOW.total_seconds() // 60),
        "active_now": len(active),
        "last_activity_at": max(latest).isoformat() if latest else None,
        "events": [{**item, "at": item["at"].isoformat()} for item in live_feed(viewer, lang=lang, now=now)],
        "freshness": freshness_summary(viewer=viewer, since=now - timedelta(hours=24)),
    }
