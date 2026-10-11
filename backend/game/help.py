"""Task-specific help behind the inventory items.

A hint potion must help with *this* step, and the architect scroll must outline
*this* solution. Both texts are written by the course author, live in
``MissionTask.data`` and stay on the server until an item is spent:

    "hints":    [{"ru": "...", "en": "..."}, ...]   progressive, easiest first
    "skeleton": {"ru": "...", "en": "..."}          an outline of the solution

Only two booleans (``has_hint``, ``has_skeleton``) are public, so the client can
switch an item off instead of charging a learner for help that does not exist.
"""

from .models import LearningEvent


def _text(value, lang):
    """A translated text: the requested language, else any other, else ''."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in (lang, "ru", "en"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def _data(task):
    return task.data if isinstance(task.data, dict) else {}


def hint_levels(task, lang="ru"):
    """The task's hints as plain strings in *lang*, easiest first."""
    raw = _data(task).get("hints")
    if not isinstance(raw, list):
        return []
    return [text for text in (_text(item, lang) for item in raw) if text]


def skeleton_text(task, lang="ru"):
    return _text(_data(task).get("skeleton"), lang)


def has_hint(task):
    return bool(hint_levels(task))


def has_skeleton(task):
    return bool(skeleton_text(task))


def next_hint(task, user, lang="ru"):
    """The hint this learner should see next, or None when the step has none.

    Every spent potion moves one level deeper; after the last level the learner
    keeps getting the last one (so a potion is never wasted on nothing).
    """
    levels = hint_levels(task, lang)
    if not levels:
        return None
    used = LearningEvent.objects.filter(
        user=user, task=task, event_type=LearningEvent.HINT_USED
    ).count()
    index = min(used, len(levels) - 1)
    return {"text": levels[index], "level": index + 1, "levels": len(levels)}


def rescue_text(task, lang="ru"):
    """The free fallback for a learner who is stuck and has no items: the first hint, else the outline."""
    levels = hint_levels(task, lang)
    return levels[0] if levels else skeleton_text(task, lang)


def rescue_allowed(user, task, profile):
    """May this learner take the free rescue hint for this step?

    Only when the help prompt is shown (3+ failures in a row, offer arm), nothing is left in
    the inventory to ask with, and the rescue was not taken for this step yet. The rescue is
    logged as its own event type, so the counts of spent items (H2) stay clean.
    """
    from .models import TaskProgress
    from .services import help_offer

    if profile.hint_scrolls > 0 or profile.ai_summons > 0:
        return False
    progress = TaskProgress.objects.filter(user=user, task=task).select_related("task").first()
    if progress is None or help_offer(progress) is None:
        return False
    return not LearningEvent.objects.filter(
        user=user, task=task, event_type=LearningEvent.HELP_RESCUE
    ).exists()
