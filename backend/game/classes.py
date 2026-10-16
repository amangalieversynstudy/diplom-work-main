"""Classes: closed courses a learner joins with a code, and who a teacher may see.

Two rules protect learners:

* a closed course (``Track.is_public`` off) is visible only to its owner and to the learners who joined it
  (``only_published`` in ``services.py``);
* a teacher sees a learner only if the learner joined one of the teacher's classes, or took a public course the
  teacher owns (the built-in courses, as before). Merely having progress in a closed course is not enough, so a
  learner who left a class disappears from that teacher's cabinet.
"""

import secrets

from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import CodeRun, Enrollment, LearningEvent, Progress, TaskProgress, Track

# no 0/O, 1/I/L: the code is read aloud and typed by hand
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def new_join_code():
    """A fresh unique class code."""
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not Track.objects.filter(join_code=code).exists():
            return code


def normalize_code(value):
    """What the learner typed or pasted -> the stored form (upper case, no spaces or dashes)."""
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def visible_learners(viewer):
    """Learners (not staff, not teachers) the viewer may see; every learner for a superuser."""
    learners = get_user_model().objects.filter(is_staff=False, is_teacher=False)
    if viewer.is_superuser:
        return learners
    # anyone who did anything in a public course of the viewer's (the built-in courses): as it always was
    sources = (
        Progress.objects.filter(
            mission__location__track__owner=viewer, mission__location__track__is_public=True
        ),
        TaskProgress.objects.filter(
            task__mission__location__track__owner=viewer, task__mission__location__track__is_public=True
        ),
        CodeRun.objects.filter(
            task__mission__location__track__owner=viewer, task__mission__location__track__is_public=True
        ),
        LearningEvent.objects.filter(
            task__mission__location__track__owner=viewer, task__mission__location__track__is_public=True
        ),
    )
    seen = Q(pk__in=Enrollment.objects.filter(track__owner=viewer).values("user_id"))
    for rows in sources:
        seen |= Q(pk__in=rows.values("user_id"))
    return learners.filter(seen)
