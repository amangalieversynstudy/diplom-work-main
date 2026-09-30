"""Personal variants of a step: every learner gets other numbers and names.

A copied answer (from a classmate or from a chat) then solves somebody else's variant and fails on
yours. The course author writes the step once with ``{{placeholders}}`` and lists the variants in
``MissionTask.data``:

    "variants": [
        {"vars": {"name": "Ари", "n": 7}, "expected_output": "Ари: 28"},
        {"vars": {"name": "Мила", "n": 9}, "expected_output": "Мила: 45"}
    ]

Placeholders are filled in the titles, the text, the starter code, the expected output (unless the
variant gives its own), the hidden check, the hints, the skeleton and, in a quiz, the options and the key. Which variant a learner gets is a
stable function of the learner and the step, so it does not change between visits and needs no table.
Anonymous visitors of the public catalogue see the first variant.

Nothing changes for a step without ``variants``.
"""

import copy
import hashlib
import re

MIN_VARIANTS = 2
MAX_VARIANTS = 30

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_TEXT_FIELDS = ("title", "title_en", "title_ru", "body", "body_en", "body_ru")
_DATA_STRINGS = ("starter", "expected_output", "hidden_check")


def variants_of(data):
    """The step's usable variants: dicts with a ``vars`` dict, in the author's order."""
    raw = data.get("variants") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    return [v for v in raw if isinstance(v, dict) and isinstance(v.get("vars"), dict)]


def variant_index(user_id, task_id, count):
    """Which of *count* variants this learner gets (0 for an anonymous visitor)."""
    if not count or user_id is None:
        return 0
    digest = hashlib.sha256(f"{user_id}:{task_id}".encode()).hexdigest()
    return int(digest[:8], 16) % count


def fill(text, variables):
    """*text* with ``{{name}}`` replaced by the variant's value; unknown names stay as written."""
    if not isinstance(text, str) or "{{" not in text:
        return text
    return _PLACEHOLDER.sub(
        lambda match: str(variables[match.group(1)]) if match.group(1) in variables else match.group(0),
        text,
    )


def _fill_pair(value, variables):
    if isinstance(value, dict):
        return {key: fill(text, variables) for key, text in value.items()}
    return fill(value, variables)


def personalize(task, user_id):
    """The task as *user_id* should see and be graded on it.

    A copy that is never saved; the original is returned untouched when the step has no variants.
    """
    data = task.data if isinstance(task.data, dict) else {}
    variants = variants_of(data)
    if not variants:
        return task
    chosen = variants[variant_index(user_id, task.pk, len(variants))]
    variables = chosen["vars"]

    personal = copy.copy(task)
    for field in _TEXT_FIELDS:
        setattr(personal, field, fill(getattr(task, field, ""), variables))

    new_data = {key: value for key, value in data.items() if key != "variants"}
    # a quiz question about the learner's own number: the options and the key follow the variant too
    if isinstance(new_data.get("correct_answer"), str):
        new_data["correct_answer"] = fill(new_data["correct_answer"], variables)
    if isinstance(new_data.get("options"), list):
        new_data["options"] = [
            {key: fill(text, variables) for key, text in option.items()} if isinstance(option, dict) else option
            for option in new_data["options"]
        ]
    for key in _DATA_STRINGS:
        if key in new_data:
            new_data[key] = fill(new_data[key], variables)
    if isinstance(chosen.get("expected_output"), str):
        new_data["expected_output"] = chosen["expected_output"]
    if isinstance(new_data.get("hints"), list):
        new_data["hints"] = [_fill_pair(item, variables) for item in new_data["hints"]]
    if "skeleton" in new_data:
        new_data["skeleton"] = _fill_pair(new_data["skeleton"], variables)
    personal.data = new_data
    return personal
