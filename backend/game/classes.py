"""Classes: closed courses a learner joins with a code, and who a teacher may see.

Rules that protect learners:

* a closed course (``Track.is_public`` off) is visible only to its owner and to the learners who joined it
  (``only_published`` in ``services.py``);
* a teacher sees a learner only if the learner joined one of the teacher's classes, or, for a vetted teacher
  (see ``is_vetted_teacher``), took a public course the teacher owns (the built-in courses, as before);
* per-learner rows (attempts, runs, events, progress) are seen per (learner, course): rows of a closed course
  count only while the learner is enrolled in it, so a learner who left a class disappears from that class's data
  even when the teacher still sees them through another course (``visible_work`` / ``visible_events``).

Every helper here treats a superuser as "sees everything" and returns before touching ``viewer.pk``: the pilot
report and the daily snapshots pass ``SimpleNamespace(is_superuser=True)``.
"""

import secrets

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q

from .models import CodeRun, Enrollment, LearningEvent, Progress, TaskProgress, Track

# no 0/O, 1/I/L: the code is read aloud and typed by hand
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8

# paths from a per-learner row to its course
TASK_TRACK = "task__mission__location__track"  # TaskProgress, CodeRun, LearningEvent tied to a step
MISSION_TRACK = "mission__location__track"  # Progress, LearningEvent tied only to a mission


def _is_superuser(viewer):
    return bool(getattr(viewer, "is_superuser", False))


def is_vetted_teacher(user):
    """A teacher the platform owner vouched for: a superuser, or a staff account (invite code or admin) that is
    not a self-service teacher. Only they own public courses, see every learner of them, count in the pilot's
    teacher measurements and give global rewards from their classes."""
    if user is None:
        return False
    if _is_superuser(user):
        return True
    return bool(getattr(user, "is_staff", False) and not getattr(user, "is_teacher", False))


def owner_scope(viewer):
    """None for a superuser (no course filter), otherwise the viewer: the owner whose courses are in scope."""
    return None if _is_superuser(viewer) else viewer


def new_join_code():
    """A fresh unique class code."""
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not Track.objects.filter(join_code=code).exists():
            return code


def with_fresh_code(write, attempts=5):
    """Run ``write(code)`` with a new class code; retry if the unique code was taken in the meantime."""
    for attempt in range(attempts):
        try:
            with transaction.atomic():
                return write(new_join_code())
        except IntegrityError:
            if attempt + 1 == attempts:
                raise
    return None  # pragma: no cover - the loop either returns or raises


def normalize_code(value):
    """What the learner typed or pasted -> the stored form (upper case, no spaces or dashes)."""
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def member_or_public(track_path, user_path="user"):
    """A row of a public course, or of a closed one whose learner is enrolled in it right now (viewer-independent)."""
    enrolled = Enrollment.objects.filter(user=OuterRef(user_path), track=OuterRef(track_path))
    return Q(**{f"{track_path}__is_public": True}) | Q(Exists(enrolled))


def visible_work(viewer, track_path, user_path="user"):
    """Per-learner rows the viewer may analyse: rows of the viewer's own courses, a closed course's rows only while
    their learner is enrolled. ``Q()`` for a superuser."""
    if _is_superuser(viewer):
        return Q()
    return Q(**{f"{track_path}__owner": viewer}) & member_or_public(track_path, user_path)


def visible_events(viewer):
    """``visible_work`` for LearningEvent, which points at a step or only at a mission."""
    if _is_superuser(viewer):
        return Q()
    return visible_work(viewer, TASK_TRACK) | visible_work(viewer, MISSION_TRACK)


def visible_learners(viewer):
    """Learners (not staff, not teachers) the viewer may see; every learner for a superuser."""
    learners = get_user_model().objects.filter(is_staff=False, is_teacher=False)
    if _is_superuser(viewer):
        return learners
    seen = Q(pk__in=Enrollment.objects.filter(track__owner=viewer).values("user_id"))
    if is_vetted_teacher(viewer):
        # anyone who did anything in a public course of a vetted teacher's (the built-in courses): as it always was.
        # A self-service teacher cannot own a public course; if one ever does, they still see only their classes.
        public_mine = {"owner": viewer, "is_public": True}
        sources = (
            Progress.objects.filter(**{f"{MISSION_TRACK}__{k}": v for k, v in public_mine.items()}),
            TaskProgress.objects.filter(**{f"{TASK_TRACK}__{k}": v for k, v in public_mine.items()}),
            CodeRun.objects.filter(**{f"{TASK_TRACK}__{k}": v for k, v in public_mine.items()}),
            LearningEvent.objects.filter(**{f"{TASK_TRACK}__{k}": v for k, v in public_mine.items()}),
        )
        for rows in sources:
            seen |= Q(pk__in=rows.values("user_id"))
    return learners.filter(seen)


def pays_globally(user, track):
    """Does work in ``track`` feed the shared economy (profile XP and level, level-up items, achievements, the
    global leaderboard)? Teachers never earn; the owner never earns in their own course. Public and track-less
    content pays; a closed class pays only when its owner is a vetted teacher. A closed class without an owner
    (the teacher's account was deleted) pays nothing."""
    if getattr(user, "can_teach", False):
        return False
    if track is None:
        return True
    if track.owner_id is not None and track.owner_id == getattr(user, "pk", None):
        return False
    if track.is_public:
        return True
    return track.owner_id is not None and is_vetted_teacher(track.owner)


def paying_tracks_q(user, track_path):
    """Q over rows reached through ``track_path``: rows whose course pays globally for ``user`` (see
    ``pays_globally``); track-less rows count."""
    vetted_owner = Q(**{f"{track_path}__owner__is_superuser": True}) | Q(
        **{f"{track_path}__owner__is_staff": True, f"{track_path}__owner__is_teacher": False}
    )
    pays = Q(**{f"{track_path}__isnull": True}) | Q(**{f"{track_path}__is_public": True}) | vetted_owner
    mine = Q(**{f"{track_path}__owner": user}) if getattr(user, "pk", None) is not None else Q(pk__in=[])
    return pays & ~mine
