"""Who and when the pilot's research figures are about: one definition for the report, H3 and the exports.

* A research participant is a learner (not staff, not a teacher) who agreed to the research and, once
  ``PILOT_STARTED_AT`` is set, signed up on or after it: rehearsal and test accounts made before the start drop out
  by themselves, without anyone having to withdraw their consent.
* The active period is ``[PILOT_STARTED_AT, PILOT_ENDED_AT)``. An outcome window that runs past its end is cut off
  (censored), not counted as "left": after a course everybody goes quiet.
* A learner is "in the course" at a moment when they have started a pilot course and not yet finished all its
  published missions. Finishing a course is not dropping out; a learner between two missions is still in it.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.dateparse import parse_datetime

from .models import Mission, Progress


def parse_moment(value):
    """An aware datetime from an ISO string; None when empty, invalid or without a time zone."""
    if not value:
        return None
    try:
        moment = parse_datetime(str(value).strip())
    except ValueError:
        return None
    if moment is None or moment.tzinfo is None:
        return None
    return moment


def pilot_period():
    """``(start, end)`` of the active period as aware datetimes; either is None when not set or not valid."""
    return (
        parse_moment(getattr(settings, "PILOT_STARTED_AT", "")),
        parse_moment(getattr(settings, "PILOT_ENDED_AT", "")),
    )


def pilot_learners():
    """Learners of the pilot cohort, with or without consent: signed up since the start, if one is set."""
    learners = get_user_model().objects.filter(is_staff=False, is_teacher=False)
    start, _ = pilot_period()
    if start is not None:
        learners = learners.filter(date_joined__gte=start)
    return learners


def research_learners():
    """Learners whose data the research figures may use: the pilot cohort with research consent."""
    return pilot_learners().filter(profile__research_consent=True)


def course_spans(user_ids):
    """``{user_id: [(start, finish or None), ...]}``: one span per pilot course (track) the learner started.

    A course is finished when every published mission of it is completed; the finish is the last completion.
    Pilot content only (see ``metrics.pilot_content_q``): a self-service teacher's class is not part of the pilot.
    """
    from .metrics import pilot_content_q  # metrics imports this module

    totals = dict(
        Mission.objects.filter(is_active=True)
        .filter(pilot_content_q("location__track"))
        .values("location__track_id")
        .annotate(n=Count("id"))
        .values_list("location__track_id", "n")
    )
    courses = {}
    rows = (
        Progress.objects.filter(user_id__in=user_ids, mission__is_active=True)
        .filter(pilot_content_q("mission__location__track"))
        .values_list("user_id", "mission__location__track_id", "started_at", "completed", "completed_at")
    )
    for user_id, track_id, started, completed, completed_at in rows:
        course = courses.setdefault((user_id, track_id), {"start": None, "done": 0, "last": None})
        if started is not None and (course["start"] is None or started < course["start"]):
            course["start"] = started
        if completed:
            course["done"] += 1
            stamp = completed_at or started
            if stamp is not None and (course["last"] is None or stamp > course["last"]):
                course["last"] = stamp
    spans = {user_id: [] for user_id in user_ids}
    for (user_id, track_id), course in courses.items():
        if course["start"] is None:
            continue
        finished = totals.get(track_id) and course["done"] >= totals[track_id]
        spans.setdefault(user_id, []).append((course["start"], course["last"] if finished else None))
    return spans


def in_course(spans, moment):
    """Was the learner inside a started, unfinished pilot course at ``moment``?"""
    return any(start <= moment and (finish is None or finish > moment) for start, finish in spans)
