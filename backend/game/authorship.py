"""Who did a solved code step: the learner alone, with the platform's help, or with signs of outside help.

Two independent sources, both about the step's solving run (the first graded run that passed):

* **Assistance** comes from what the platform itself recorded: hint potions, the skeleton scroll and the
  AI mentor used on that step before it was solved. It is exact.
* **Signals** come from the editor's counts of how the code got into the editor (typed or pasted).
  The editor sends them, so a learner who talks to the API directly can leave them out or forge them:
  they point to steps worth a look and never prove anything. Only counts are kept, never keystrokes
  or the pasted text.

Nothing here decides anything about a learner: the teacher sees the facts and the reasons.
"""

from .models import CodeRun, LearningEvent
from .metrics import scoped_tasks

# provenance fields the editor may send; anything else is dropped, values are clamped
PROVENANCE_FIELDS = (
    "pasted_chars",
    "typed_chars",
    "paste_count",
    "edit_events",
    "edits_after_paste",
    "elapsed_ms",
)
_MAX_VALUE = 10_000_000

# thresholds of the signals (see ``signals_for``)
LARGE_PASTE_MIN_CHARS = 60
LARGE_PASTE_SHARE = 0.6
FEW_EDITS_AFTER_PASTE = 2
FAST_TYPING_MIN_CHARS = 80
FAST_TYPING_CHARS_PER_SECOND = 10

# what a learner used on a step, weakest to strongest
ASSISTANCE_LEVELS = ("independent", "hint", "skeleton", "mentor")
_EVENT_LEVEL = {
    LearningEvent.HINT_USED: "hint",
    LearningEvent.SKELETON_USED: "skeleton",
    LearningEvent.AI_HINT_USED: "mentor",
    LearningEvent.AI_MENTOR_USED: "mentor",
}


def clean_provenance(raw):
    """The editor's counts as a dict of clamped ints; {} for anything that is not a dict of numbers."""
    if not isinstance(raw, dict):
        return {}
    cleaned = {}
    for field in PROVENANCE_FIELDS:
        value = raw.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        cleaned[field] = max(0, min(_MAX_VALUE, int(value)))
    return cleaned


def paste_share(provenance, code_length):
    """Share of the final code that arrived by pasting (0..1), or None without editor data."""
    if not provenance or not code_length:
        return None
    return min(1.0, provenance.get("pasted_chars", 0) / code_length)


def signals_for(run):
    """[{code, ...values}] describing the solving run; empty when nothing stands out."""
    data = run.provenance or {}
    if not data:
        return [{"code": "no_editor_data"}]
    signals = []
    pasted = data.get("pasted_chars", 0)
    share = paste_share(data, run.code_length) or 0
    if pasted >= LARGE_PASTE_MIN_CHARS and share >= LARGE_PASTE_SHARE:
        edits = data.get("edits_after_paste", 0)
        signals.append(
            {
                "code": "paste_then_run" if edits <= FEW_EDITS_AFTER_PASTE else "large_paste",
                "share": round(share * 100),
                "edits": edits,
            }
        )
    typed = data.get("typed_chars", 0)
    seconds = max(1, data.get("elapsed_ms", 0) // 1000)
    if typed >= FAST_TYPING_MIN_CHARS and typed / seconds > FAST_TYPING_CHARS_PER_SECOND:
        signals.append({"code": "fast_typing", "chars": typed, "seconds": seconds})
    return signals


def _title(obj, lang):
    return obj.get_localized_title(lang) or f"#{obj.pk}"


def authorship_report(student, viewer, *, lang="ru"):
    """Per solved code step of *student* inside *viewer*'s courses: assistance and signals."""
    tasks = {
        task.pk: task for task in scoped_tasks(viewer).filter(task_type="code")
    }
    solving = {}
    runs = (
        CodeRun.objects.filter(
            user=student, task_id__in=list(tasks), passed=True, after_solved=False
        )
        .order_by("created_at")
    )
    for run in runs:
        solving.setdefault(run.task_id, run)

    helped = {}
    for event in LearningEvent.objects.filter(
        user=student, task_id__in=list(solving), event_type__in=list(_EVENT_LEVEL)
    ):
        run = solving.get(event.task_id)
        if run is not None and event.created_at <= run.created_at:
            helped.setdefault(event.task_id, []).append(event.event_type)

    steps = []
    for task_id, task in tasks.items():
        run = solving.get(task_id)
        if run is None:
            continue
        events = helped.get(task_id, [])
        level = max((_EVENT_LEVEL[e] for e in events), key=ASSISTANCE_LEVELS.index, default="independent")
        share = paste_share(run.provenance, run.code_length)
        steps.append(
            {
                "task_id": task_id,
                "title": _title(task, lang),
                "mission": _title(task.mission, lang),
                "attempts": run.attempt_no or 1,
                "solved_at": run.created_at,
                "assistance": level,
                "help_uses": {
                    "hint": events.count(LearningEvent.HINT_USED),
                    "skeleton": events.count(LearningEvent.SKELETON_USED),
                    "mentor": events.count(LearningEvent.AI_HINT_USED)
                    + events.count(LearningEvent.AI_MENTOR_USED),
                },
                "paste_share": None if share is None else round(share * 100),
                "signals": signals_for(run),
            }
        )

    summary = {
        "solved": len(steps),
        "independent": sum(1 for s in steps if s["assistance"] == "independent"),
        "assisted": sum(1 for s in steps if s["assistance"] != "independent"),
        "flagged": sum(1 for s in steps if any(sig["code"] != "no_editor_data" for sig in s["signals"])),
    }
    return {"summary": summary, "steps": steps}
