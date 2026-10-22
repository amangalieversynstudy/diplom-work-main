"""Who did a solved code step: the learner alone, with the platform's help, or with signs of outside help.

Three independent sources, all about the step's solving run (the first graded run that passed):

* **Assistance** comes from what the platform itself recorded: hint potions, the skeleton scroll and the
  AI mentor used on that step before it was solved. It is exact.
* **Signals** come from the editor's counts of how the code got into the editor (typed or pasted).
  The editor sends them, so a learner who talks to the API directly can leave them out or forge them:
  they point to steps worth a look and never prove anything. Only counts are kept, never keystrokes
  or the pasted text.
* **The code itself** (``codeanalysis``): does the solution use a construct the course author marked as
  not taught yet for this step, and did another learner of the same teacher hand in a solution of the same
  structure. The code is not kept, only a structural fingerprint.

Nothing here decides anything about a learner: the teacher sees the facts and the reasons.
"""

from .metrics import scoped_tasks
from .models import CodeRun, LearningEvent, TaskProgress
from .variants import variant_index, variants_of
from .classes import TASK_TRACK, visible_work
from .warning import scoped_learners

# provenance fields the editor may send; anything else is dropped, values are clamped
PROVENANCE_FIELDS = (
    "pasted_chars",
    "typed_chars",
    "paste_count",
    "edit_events",
    "edits_after_paste",
    "elapsed_ms",
    # time on the step and pauses (all counts / milliseconds, never what the learner did)
    "active_ms",
    "away_ms",
    "away_count",
    "longest_away_ms",
    "pause_count",
    "longest_pause_ms",
    "first_key_ms",
    "paste_after_away",
)
_MAX_VALUE = 10_000_000

# Expert thresholds, not calibrated on data; the signals are only hints for a conversation.
FAST_SOLVE_MIN_CHARS = 80  # the learner added this many characters (typed + pasted; the starter code does not count) ...
FAST_SOLVE_MAX_MS = 20_000  # ... in under 20 s can hardly be typed and reasoned about
AWAY_PASTE_MIN_COUNT = 1  # pastes right after returning to the tab
AWAY_PASTE_MIN_CHARS = 40

# thresholds of the signals (see ``signals_for``)
LARGE_PASTE_MIN_CHARS = 60
LARGE_PASTE_SHARE = 0.6
FEW_EDITS_AFTER_PASTE = 2
FAST_TYPING_MIN_CHARS = 80
FAST_TYPING_CHARS_PER_SECOND = 10
# solutions smaller than this are compared by nobody: a three-line exercise has one natural answer
SIMILAR_MIN_NODES = 30

# wrong answers to the "explain your solution" question that, together with other signals, say that
# the solution was not understood (with four options a guess alone fails twice about half the time)
EXPLAIN_MISSED_AFTER = 2

# what a learner used on a step, weakest to strongest
ASSISTANCE_LEVELS = ("independent", "hint", "skeleton", "mentor")
_EVENT_LEVEL = {
    LearningEvent.HINT_USED: "hint",
    LearningEvent.HELP_RESCUE: "hint",  # the free hint after repeated failures is platform help too
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


def signals_for(run, *, not_yet=(), twins=()):
    """[{code, ...values}] describing the solving run; empty when nothing stands out.

    ``not_yet`` are the constructs the author marked as not taught for this step, ``twins`` the
    usernames of other learners whose solving run has the same structure.
    """
    signals = []
    early = sorted(set(run.constructs or []) & set(not_yet))
    if early:
        signals.append({"code": "untaught_construct", "constructs": ", ".join(early)})
    if twins:
        signals.append({"code": "same_as_others", "count": len(twins), "with": ", ".join(list(twins)[:3])})
    data = run.provenance or {}
    if not data:
        return signals + [{"code": "no_editor_data"}]
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
    elapsed = data.get("elapsed_ms", 0)
    added = typed + pasted  # only what the learner put in: a starter code they merely edited must not count
    if added >= FAST_SOLVE_MIN_CHARS and 0 < elapsed < FAST_SOLVE_MAX_MS:
        signals.append({"code": "fast_solve", "seconds": elapsed // 1000, "chars": added})
    after_away = data.get("paste_after_away", 0)
    if after_away >= AWAY_PASTE_MIN_COUNT and pasted >= AWAY_PASTE_MIN_CHARS:
        signals.append({"code": "away_then_paste", "count": after_away})
    return signals


def timing_of(provenance):
    """Seconds view of the time fields for the teacher; None without editor data, None per missing key."""
    if not provenance:
        return None

    def sec(key):
        return round(provenance[key] / 1000) if key in provenance else None

    return {
        "elapsed_s": sec("elapsed_ms"),
        "active_s": sec("active_ms"),
        "away_s": sec("away_ms"),
        "away_count": provenance.get("away_count"),
        "pause_count": provenance.get("pause_count"),
        "longest_pause_s": sec("longest_pause_ms"),
        "first_key_s": sec("first_key_ms"),
    }


def _explain_result(progress):
    """{"status", "wrong"} of the learner's answers to the explain question, None if there is none."""
    if progress is None or progress.attempts == 0 and progress.status != "completed":
        return {"status": "none", "wrong": 0}
    solved = progress.status == "completed"
    wrong = max(0, progress.attempts - 1) if solved else progress.attempts
    if not solved:
        return {"status": "unsolved", "wrong": wrong}
    return {"status": "first_try" if wrong == 0 else "retried", "wrong": wrong}


def _title(obj, lang):
    return obj.get_localized_title(lang) or f"#{obj.pk}"


def _context(viewer):
    """What does not depend on the learner: the viewer's code steps and their explain questions."""
    tasks = {task.pk: task for task in scoped_tasks(viewer).filter(task_type="code")}
    explain_of = {}
    for candidate in scoped_tasks(viewer).filter(task_type="quiz"):
        about = (candidate.data or {}).get("about") if candidate.kind == "explain" else None
        if isinstance(about, int) and about in tasks:
            explain_of[about] = candidate
    return {"tasks": tasks, "explain_of": explain_of}


def authorship_report(student, viewer, *, lang="ru", context=None):
    """Per solved code step of *student* inside *viewer*'s courses: assistance and signals."""
    context = context or _context(viewer)
    tasks = context["tasks"]
    solving = {}
    runs = (
        CodeRun.objects.filter(
            user=student, task_id__in=list(tasks), passed=True, after_solved=False
        )
        .filter(visible_work(viewer, TASK_TRACK))  # a class the learner left is not shown any more
        .order_by("created_at")
    )
    for run in runs:
        solving.setdefault(run.task_id, run)

    # other learners of this teacher who solved the same step with the same structure
    twins = {}
    prints = {run.fingerprint for run in solving.values() if run.fingerprint and run.ast_nodes >= SIMILAR_MIN_NODES}
    if prints:
        others = (
            CodeRun.objects.filter(
                task_id__in=list(solving),
                fingerprint__in=prints,
                passed=True,
                after_solved=False,
                user__in=scoped_learners(viewer),
            )
            .filter(visible_work(viewer, TASK_TRACK))
            .exclude(user=student)
            .select_related("user")
            .order_by("created_at")
        )
        for other in others:
            mine = solving.get(other.task_id)
            count = len(variants_of(tasks[other.task_id].data))
            if count > 1 and variant_index(other.user_id, other.task_id, count) == variant_index(
                student.pk, other.task_id, count
            ):
                continue  # the same variant has the same natural solution: not a sign of anything
            if mine is not None and mine.fingerprint == other.fingerprint:
                twins.setdefault(other.task_id, [])
                if other.user.username not in twins[other.task_id]:
                    twins[other.task_id].append(other.user.username)

    # the "explain your solution" question that follows a code step, and how the learner did on it
    explain_of = {about: task for about, task in context["explain_of"].items() if about in solving}
    explain_progress = {
        row.task_id: row
        for row in TaskProgress.objects.filter(user=student, task_id__in=[t.pk for t in explain_of.values()])
    }

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
        signals = signals_for(
            run,
            not_yet=(task.data or {}).get("not_yet", []) if isinstance(task.data, dict) else [],
            twins=twins.get(task_id, []),
        )
        explain = _explain_result(explain_progress.get(explain_of[task_id].pk)) if task_id in explain_of else None
        if explain and explain["wrong"] >= EXPLAIN_MISSED_AFTER and any(
            sig["code"] != "no_editor_data" for sig in signals
        ):
            signals.append({"code": "explain_missed", "wrong": explain["wrong"]})
        steps.append(
            {
                "task_id": task_id,
                "title": _title(task, lang),
                "mission": _title(task.mission, lang),
                "attempts": run.attempt_no or 1,
                "solved_at": run.created_at,
                "assistance": level,
                "help_uses": {
                    "hint": events.count(LearningEvent.HINT_USED) + events.count(LearningEvent.HELP_RESCUE),
                    "skeleton": events.count(LearningEvent.SKELETON_USED),
                    "mentor": events.count(LearningEvent.AI_HINT_USED)
                    + events.count(LearningEvent.AI_MENTOR_USED),
                },
                "paste_share": None if share is None else round(share * 100),
                "explain": explain,
                "timing": timing_of(run.provenance),
                "signals": signals,
            }
        )

    summary = {
        "solved": len(steps),
        "independent": sum(1 for s in steps if s["assistance"] == "independent"),
        "assisted": sum(1 for s in steps if s["assistance"] != "independent"),
        "flagged": sum(1 for s in steps if any(sig["code"] != "no_editor_data" for sig in s["signals"])),
    }
    return {"summary": summary, "steps": steps}


def authorship_overview(viewer, *, limit=8):
    """Learners of *viewer* with signs worth a conversation, most first.

    [{"id", "username", "flagged", "solved"}]: only learners with at least one solved code step that
    carries a sign other than "no editor data". It says where to look first, nothing more.
    """
    context = _context(viewer)
    if not context["tasks"]:
        return []
    # a learner who has not solved a code step has nothing to report: do not build a report for them
    solvers = CodeRun.objects.filter(
        task_id__in=list(context["tasks"]), passed=True, after_solved=False
    ).filter(visible_work(viewer, TASK_TRACK)).values("user_id")
    rows = []
    for student in scoped_learners(viewer).filter(pk__in=solvers):
        summary = authorship_report(student, viewer, context=context)["summary"]
        if summary["flagged"]:
            rows.append(
                {
                    "id": student.pk,
                    "username": student.username,
                    "flagged": summary["flagged"],
                    "solved": summary["solved"],
                }
            )
    rows.sort(key=lambda row: (-row["flagged"], -row["solved"], row["username"]))
    return rows[:limit]
