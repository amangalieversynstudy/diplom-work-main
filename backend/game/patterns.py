"""Behavioral pattern analysis of learners (attempts, pauses, help usage, time on step, tab switches).

Extracts per-learner behavioral indicators from ``TaskProgress``, ``LearningEvent``, and
``CodeRun.provenance`` and classifies each learner into an interpretable behavioral profile:

* ``independent`` — Самостоятельный планомерный (low attempts, minimal help/tab switching)
* ``help_assisted`` — Опора на подсказки и ИИ (frequent hints, code skeletons, or AI mentor)
* ``trial_and_error`` — Метод проб и ошибок (high attempts per step without heavy hints/tab switches)
* ``fragmented`` — Прерывистый / переключения вкладки (frequent focus loss, long pauses, or paste after away)
* ``insufficient_data`` — Мало данных (no attempted graded steps yet)
"""

from collections import defaultdict
from statistics import median

from .classes import TASK_TRACK, owner_scope, visible_learners, visible_work
from .models import CodeRun, LearningEvent, MissionTask, TaskProgress

GRADED_TYPES = ("quiz", "code")

HELP_EVENT_TYPES = (
    LearningEvent.HINT_USED,
    LearningEvent.HELP_RESCUE,
    LearningEvent.SKELETON_USED,
    LearningEvent.AI_HINT_USED,
    LearningEvent.AI_MENTOR_USED,
)

PATTERN_CODES = ("independent", "help_assisted", "trial_and_error", "fragmented")

MIN_PATTERN_STEPS = 1
HELP_RATE_MIN = 0.40
HELP_EVENTS_MIN = 2
TRIAL_ATTEMPTS_MIN = 2.5
AWAY_COUNT_MIN = 2.0
PAUSE_COUNT_MIN = 3.0


def classify_behavioral_pattern(
    *,
    attempted_steps,
    mean_attempts,
    help_rate,
    help_events,
    mean_pauses,
    mean_away_count,
    paste_after_away_total,
):
    """Assign a single interpretable behavioral pattern code from per-learner indicators."""
    if not attempted_steps or attempted_steps < MIN_PATTERN_STEPS:
        return "insufficient_data"

    if (
        (paste_after_away_total or 0) >= 1
        or (mean_away_count is not None and mean_away_count >= AWAY_COUNT_MIN)
        or (mean_pauses is not None and mean_pauses >= PAUSE_COUNT_MIN)
    ):
        return "fragmented"

    if (help_rate is not None and help_rate >= HELP_RATE_MIN) or (help_events or 0) >= HELP_EVENTS_MIN:
        return "help_assisted"

    if mean_attempts is not None and mean_attempts >= TRIAL_ATTEMPTS_MIN:
        return "trial_and_error"

    return "independent"


def _extract_learner_features(learner_ids, task_ids):
    """Return {user_id: feature_dict} for ``learner_ids`` scoped to ``task_ids``."""
    if not learner_ids:
        return {}

    learner_set = set(learner_ids)
    task_set = set(task_ids) if task_ids else set()

    attempts_by_user = defaultdict(list)
    solved_by_user = defaultdict(int)
    attempted_tasks_by_user = defaultdict(set)

    if task_set:
        for tp in (
            TaskProgress.objects.filter(user_id__in=learner_set, task_id__in=task_set)
            .only("user_id", "task_id", "status", "attempts")
        ):
            if tp.status == "completed" or tp.attempts > 0:
                attempts_by_user[tp.user_id].append(max(tp.attempts, 1))
                attempted_tasks_by_user[tp.user_id].add(tp.task_id)
                if tp.status == "completed":
                    solved_by_user[tp.user_id] += 1

    help_events_by_user = defaultdict(int)
    help_tasks_by_user = defaultdict(set)
    if task_set:
        for ev in (
            LearningEvent.objects.filter(
                user_id__in=learner_set,
                task_id__in=task_set,
                event_type__in=HELP_EVENT_TYPES,
            ).only("user_id", "task_id", "event_type")
        ):
            help_events_by_user[ev.user_id] += 1
            if ev.task_id:
                help_tasks_by_user[ev.user_id].add(ev.task_id)
                if ev.task_id not in attempted_tasks_by_user[ev.user_id]:
                    attempted_tasks_by_user[ev.user_id].add(ev.task_id)
                    attempts_by_user[ev.user_id].append(1)

    active_sec_by_user = defaultdict(list)
    pauses_by_user = defaultdict(list)
    away_by_user = defaultdict(list)
    paste_after_away_by_user = defaultdict(int)
    runs_count_by_user = defaultdict(int)

    if task_set:
        for run in (
            CodeRun.objects.filter(user_id__in=learner_set, task_id__in=task_set)
            .only("user_id", "task_id", "passed", "provenance")
        ):
            uid = run.user_id
            runs_count_by_user[uid] += 1
            if run.task_id and run.task_id not in attempted_tasks_by_user[uid]:
                attempted_tasks_by_user[uid].add(run.task_id)
                attempts_by_user[uid].append(1)

            prov = run.provenance if isinstance(run.provenance, dict) else {}
            if not prov:
                continue

            if run.passed:
                ms = prov.get("active_ms") or prov.get("elapsed_ms") or 0
                if isinstance(ms, (int, float)) and ms > 0:
                    active_sec_by_user[uid].append(round(ms / 1000.0, 1))

            if "pause_count" in prov and isinstance(prov["pause_count"], (int, float)):
                pauses_by_user[uid].append(float(prov["pause_count"]))
            elif "elapsed_ms" in prov:
                pauses_by_user[uid].append(0.0)

            if "away_count" in prov and isinstance(prov["away_count"], (int, float)):
                away_by_user[uid].append(float(prov["away_count"]))
            elif "elapsed_ms" in prov:
                away_by_user[uid].append(0.0)

            paa = prov.get("paste_after_away")
            if isinstance(paa, (int, float)) and paa > 0:
                paste_after_away_by_user[uid] += int(paa)

    out = {}
    for uid in learner_ids:
        att_list = attempts_by_user.get(uid, [])
        attempted_steps = len(attempted_tasks_by_user.get(uid, set()))
        solved_steps = solved_by_user.get(uid, 0)
        mean_attempts = round(sum(att_list) / len(att_list), 2) if att_list else None

        help_events = help_events_by_user.get(uid, 0)
        assisted_steps = len(help_tasks_by_user.get(uid, set()))
        help_rate = round(assisted_steps / attempted_steps, 4) if attempted_steps else None

        act_list = active_sec_by_user.get(uid, [])
        median_active_s = round(float(median(act_list)), 1) if act_list else None

        pause_list = pauses_by_user.get(uid, [])
        mean_pauses = round(sum(pause_list) / len(pause_list), 2) if pause_list else None

        away_list = away_by_user.get(uid, [])
        mean_away_count = round(sum(away_list) / len(away_list), 2) if away_list else None

        paste_after_away_total = paste_after_away_by_user.get(uid, 0)

        code = classify_behavioral_pattern(
            attempted_steps=attempted_steps,
            mean_attempts=mean_attempts,
            help_rate=help_rate,
            help_events=help_events,
            mean_pauses=mean_pauses,
            mean_away_count=mean_away_count,
            paste_after_away_total=paste_after_away_total,
        )

        out[uid] = {
            "code": code,
            "attempted_steps": attempted_steps,
            "solved_steps": solved_steps,
            "mean_attempts": mean_attempts,
            "help_events": help_events,
            "assisted_steps": assisted_steps,
            "help_rate": help_rate,
            "code_runs": runs_count_by_user.get(uid, 0),
            "median_active_s": median_active_s,
            "mean_pauses": mean_pauses,
            "mean_away_count": mean_away_count,
            "paste_after_away_total": paste_after_away_total,
        }
    return out


def compute_behavioral_patterns(
    viewer,
    *,
    track_id=None,
    learner_ids=None,
    task_ids=None,
    performance_by_user=None,
):
    """Aggregate behavioral pattern profiles across a teacher's or course's learners."""
    if task_ids is None:
        owner = owner_scope(viewer)
        tasks_qs = MissionTask.objects.filter(
            mission__location__track__is_active=True,
            task_type__in=GRADED_TYPES,
        )
        if owner is not None:
            tasks_qs = tasks_qs.filter(mission__location__track__owner=owner)
        if track_id is not None:
            tasks_qs = tasks_qs.filter(mission__location__track_id=track_id)
        task_ids = list(tasks_qs.values_list("id", flat=True))

    if learner_ids is None:
        learner_ids = list(visible_learners(viewer).values_list("id", flat=True))

    features_by_user = _extract_learner_features(learner_ids, task_ids)

    grouped = defaultdict(list)
    for uid, feat in features_by_user.items():
        grouped[feat["code"]].append((uid, feat))

    classified_learners = sum(len(grouped[c]) for c in PATTERN_CODES)
    perf_map = performance_by_user or {}

    profiles = []
    dominant_pattern = None
    best_count = 0

    for code in PATTERN_CODES:
        items = grouped.get(code, [])
        count = len(items)
        if count > best_count:
            best_count = count
            dominant_pattern = code

        share = round(count / classified_learners, 4) if classified_learners else None

        perfs = [
            perf_map[uid]
            for uid, _ in items
            if uid in perf_map and perf_map[uid] is not None
        ]
        atts = [f["mean_attempts"] for _, f in items if f["mean_attempts"] is not None]
        helps = [f["help_rate"] for _, f in items if f["help_rate"] is not None]
        aways = [f["mean_away_count"] for _, f in items if f["mean_away_count"] is not None]
        pauses = [f["mean_pauses"] for _, f in items if f["mean_pauses"] is not None]
        actives = [f["median_active_s"] for _, f in items if f["median_active_s"] is not None]

        profiles.append({
            "code": code,
            "count": count,
            "share": share,
            "mean_performance": round(sum(perfs) / len(perfs), 1) if perfs else None,
            "mean_attempts": round(sum(atts) / len(atts), 2) if atts else None,
            "mean_help_rate": round(sum(helps) / len(helps), 4) if helps else None,
            "mean_away_count": round(sum(aways) / len(aways), 2) if aways else None,
            "mean_pauses": round(sum(pauses) / len(pauses), 2) if pauses else None,
            "median_active_s": round(float(median(actives)), 1) if actives else None,
        })

    return {
        "total_learners": len(learner_ids),
        "classified_learners": classified_learners,
        "insufficient_data_count": len(grouped.get("insufficient_data", [])),
        "dominant_pattern": dominant_pattern,
        "thresholds": {
            "help_rate_min": HELP_RATE_MIN,
            "help_events_min": HELP_EVENTS_MIN,
            "trial_attempts_min": TRIAL_ATTEMPTS_MIN,
            "away_count_min": AWAY_COUNT_MIN,
            "pause_count_min": PAUSE_COUNT_MIN,
        },
        "profiles": profiles,
    }


def student_behavioral_patterns_map(viewer, learner_ids, *, track_id=None):
    """Return {user_id: feature_dict} for ``learner_ids`` scoped to ``viewer``'s courses."""
    if not learner_ids:
        return {}
    owner = owner_scope(viewer)
    tasks_qs = MissionTask.objects.filter(
        mission__location__track__is_active=True,
        task_type__in=GRADED_TYPES,
    )
    if owner is not None:
        tasks_qs = tasks_qs.filter(mission__location__track__owner=owner)
    if track_id is not None:
        tasks_qs = tasks_qs.filter(mission__location__track_id=track_id)
    task_ids = list(tasks_qs.values_list("id", flat=True))
    return _extract_learner_features(learner_ids, task_ids)


def student_behavioral_pattern(student, *, owner=None, track_id=None):
    """Return the behavioral pattern dict for a single learner."""
    tasks_qs = MissionTask.objects.filter(
        mission__location__track__is_active=True,
        task_type__in=GRADED_TYPES,
    )
    if owner is not None:
        tasks_qs = tasks_qs.filter(mission__location__track__owner=owner)
    if track_id is not None:
        tasks_qs = tasks_qs.filter(**{f"{TASK_TRACK}__id": track_id})
    task_ids = list(tasks_qs.values_list("id", flat=True))
    return _extract_learner_features([student.pk], task_ids).get(
        student.pk,
        {
            "code": "insufficient_data",
            "attempted_steps": 0,
            "solved_steps": 0,
            "mean_attempts": None,
            "help_events": 0,
            "assisted_steps": 0,
            "help_rate": None,
            "code_runs": 0,
            "median_active_s": None,
            "mean_pauses": None,
            "mean_away_count": None,
            "paste_after_away_total": 0,
        },
    )
