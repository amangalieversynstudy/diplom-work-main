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
