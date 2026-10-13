"""The pilot's weekly report: who took part, how it is going, does help help.

Everything is computed from data the platform already stores. The numbers that go
into the thesis cover only learners who agreed to the research
(``Profile.research_consent``); the others are only counted, never analysed
(nothing personal is printed, only counts and rates).
"""

import math
from datetime import timedelta
from statistics import median
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.utils import timezone

from users.models import Profile

from .live import freshness_summary
from .snapshots import h3_summary
from .metrics import DEFAULT_INACTIVE_DAYS, _last_activity, compute_metrics
from .models import CodeRun, LearningEvent, MissionTask, Progress, TaskProgress
from .services import ARM_OFFER, HELP_AFTER_FAILURES, help_arm
from .usability import usability_summary
from .warning import assess_students

MIN_ARM_SIZE = 30  # below this the arm comparison is anecdote, not evidence
WEEKS = 4

_OWNER = SimpleNamespace(is_superuser=True)  # the researcher sees every course


def two_proportions(x1, n1, x2, n2):
    """Difference of two shares with a 95% interval and a two-sided p-value.

    Normal approximation: fine for hundreds of pairs, optimistic for dozens
    (the report says so). ``None`` if either group is empty.
    """
    if not n1 or not n2:
        return None
    p1, p2 = x1 / n1, x2 / n2
    diff = p1 - p2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    pooled = (x1 + x2) / (n1 + n2)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = diff / se0 if se0 else 0.0
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return {
        "diff": round(diff, 4),
        "ci_low": round(diff - 1.96 * se, 4),
        "ci_high": round(diff + 1.96 * se, 4),
        "p_value": round(p_value, 4),
    }


def _weekly_active(learner_ids, now, weeks):
    since = now - timedelta(weeks=weeks)
    seen = {}
    rows = list(
        LearningEvent.objects.filter(user_id__in=learner_ids, created_at__gte=since)
        .values_list("user_id", "created_at")
    ) + list(
        CodeRun.objects.filter(user_id__in=learner_ids, created_at__gte=since)
        .values_list("user_id", "created_at")
    )
    for user_id, stamp in rows:
        week = int((now - stamp).days // 7)
        seen.setdefault(week, set()).add(user_id)
    return [len(seen.get(week, ())) for week in range(weeks - 1, -1, -1)]  # oldest first


def help_experiment(now, learner_ids=None):
    """Outcomes after the help threshold, per experiment arm.

    ``learner_ids`` limits the analysis to those learners (the report passes the consenting ones).
    """
    offered = LearningEvent.objects.filter(event_type=LearningEvent.HELP_OFFERED, task__isnull=False)
    if learner_ids is not None:
        offered = offered.filter(user_id__in=learner_ids)
    events = list(offered.values_list("user_id", "task_id", "created_at", "meta"))
    users = {user_id for user_id, *_ in events}
    last_seen = _last_activity(users)
    cutoff = now - timedelta(days=DEFAULT_INACTIVE_DAYS)
    progress = {
        (row["user_id"], row["task_id"]): row
        for row in TaskProgress.objects.filter(user_id__in=users).values(
            "user_id", "task_id", "status", "attempts"
        )
    }
    helped_after = {}
    rescued_after = {}
    for user_id, task_id, stamp, event_type in LearningEvent.objects.filter(
        user_id__in=users,
        event_type__in=(
            LearningEvent.HINT_USED,
            LearningEvent.SKELETON_USED,
            LearningEvent.AI_HINT_USED,
            LearningEvent.AI_MENTOR_USED,
            LearningEvent.HELP_RESCUE,  # the free hint is part of what the "banner" arm receives
        ),
    ).values_list("user_id", "task_id", "created_at", "event_type"):
        helped_after.setdefault((user_id, task_id), []).append(stamp)
        if event_type == LearningEvent.HELP_RESCUE:
            rescued_after.setdefault((user_id, task_id), []).append(stamp)

    arms = {}
    for user_id, task_id, stamp, meta in events:
        arm = (meta or {}).get("arm") or help_arm(user_id)
        row = progress.get((user_id, task_id))
        solved = bool(row) and row["status"] == "completed"
        bucket = arms.setdefault(
            arm, {"pairs": 0, "solved": 0, "dropped": 0, "extra": [], "helped": 0, "rescued": 0}
        )
        bucket["pairs"] += 1
        bucket["solved"] += solved
        if solved:
            bucket["extra"].append(max(0, row["attempts"] - HELP_AFTER_FAILURES))
        elif last_seen.get(user_id, now - timedelta(days=3650)) < cutoff:
            bucket["dropped"] += 1
        bucket["helped"] += any(t > stamp for t in helped_after.get((user_id, task_id), ()))
        bucket["rescued"] += any(t > stamp for t in rescued_after.get((user_id, task_id), ()))

    result = {}
    for arm, b in arms.items():
        pairs = b["pairs"]
        result[arm] = {
            "pairs": pairs,
            "solved": b["solved"],
            "solve_rate": round(100 * b["solved"] / pairs, 1),
            "dropped": b["dropped"],
            "dropout_rate": round(100 * b["dropped"] / pairs, 1),
            "extra_attempts": round(sum(b["extra"]) / len(b["extra"]), 2) if b["extra"] else None,
            "helped_after_rate": round(100 * b["helped"] / pairs, 1),
            "rescued_after_rate": round(100 * b["rescued"] / pairs, 1),
        }
    offer, control = arms.get(ARM_OFFER), arms.get("control")
    comparison = None
    if offer and control:
        comparison = {
            "solved": two_proportions(offer["solved"], offer["pairs"], control["solved"], control["pairs"]),
            "dropped": two_proportions(offer["dropped"], offer["pairs"], control["dropped"], control["pairs"]),
            "enough": min(offer["pairs"], control["pairs"]) >= MIN_ARM_SIZE,
        }
    return {"arms": result, "comparison": comparison}


def sandbox_health():
    runs = list(CodeRun.objects.values_list("outcome", "duration_ms"))
    total = len(runs)
    if not total:
        return {"runs": 0}
    share = lambda outcome: round(100 * sum(1 for o, _ in runs if o == outcome) / total, 1)  # noqa: E731
    return {
        "runs": total,
        "runner_error_rate": share("runner_error"),
        "timeout_rate": share("timeout"),
        "output_limit_rate": share("output_limit"),
        "median_ms": int(median(ms for _, ms in runs)),
    }


def build_report(now=None):
    """Everything the weekly pilot report shows, as plain data."""
    now = now or timezone.now()
    learners = get_user_model().objects.filter(is_staff=False)
    registered = learners.count()
    # Only learners who agreed are analysed; the rest are counted (n), never looked at.
    consenting_ids = set(
        Profile.objects.filter(user__in=learners, research_consent=True).values_list("user_id", flat=True)
    )
    learner_ids = sorted(consenting_ids)
    consenting = len(consenting_ids)
    footprint_of = lambda ids: set(  # noqa: E731
        LearningEvent.objects.filter(user_id__in=ids).values_list("user_id", flat=True)
    ) | set(CodeRun.objects.filter(user_id__in=ids).values_list("user_id", flat=True))
    with_footprint = footprint_of(learner_ids)
    footprint_without_consent = footprint_of(
        list(learners.exclude(pk__in=consenting_ids).values_list("pk", flat=True))
    )
    started = set(
        Progress.objects.filter(user_id__in=learner_ids, started_at__isnull=False)
        .values_list("user_id", flat=True)
    )
    finished = set(
        Progress.objects.filter(user_id__in=learner_ids, completed=True)
        .values_list("user_id", flat=True)
    )
    solved_steps = TaskProgress.objects.filter(
        user_id__in=learner_ids, status="completed"
    ).count()

    metrics = compute_metrics(_OWNER, now=now, consented_only=True)
    warnings = assess_students(_OWNER, now=now, consented_only=True)
    opened = {row["task_id"] for row in metrics["tasks"] if row["opened"]}
    all_steps = MissionTask.objects.filter(mission__is_active=True).count()

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "participants": {
            "learners": registered,
            "consented": consenting,
            "excluded_without_consent": registered - consenting,
            "with_activity": len(with_footprint),
            "started_a_mission": len(started),
            "finished_a_mission": len(finished),
            "active_by_week": _weekly_active(learner_ids, now, WEEKS),
            "activity_without_consent": len(footprint_without_consent),
        },
        "steps": {
            "solved": solved_steps,
            "per_active_learner": round(solved_steps / len(with_footprint), 1) if with_footprint else None,
            "never_opened": all_steps - len(opened),
            "total": all_steps,
        },
        "kpi": metrics["kpi"],
        "failure_curve": metrics["failure_curve"],
        "critical_threshold": metrics["critical_threshold"],
        "ews": {
            "high": sum(a["level"] == "high" for a in warnings.values()),
            "medium": sum(a["level"] == "medium" for a in warnings.values()),
        },
        "help_experiment": help_experiment(now, learner_ids),
        "h3": h3_summary(now=now),
        "sandbox": sandbox_health(),
        "dashboard": {"freshness": freshness_summary(), "usability": usability_summary()},
        "metrics_meta": metrics["meta"],
    }


def _fmt(value, unit=""):
    return "—" if value is None else f"{value}{unit}"


def render_markdown(report):
    p, s, k = report["participants"], report["steps"], report["kpi"]
    lines = [
        f"# Отчёт пилота — {report['generated_at']}",
        "",
        "## Участники",
        "",
        f"- Учеников зарегистрировано: **{p['learners']}**, согласились на исследование: **{p['consented']}**. "
        f"**Все цифры ниже посчитаны только по {p['consented']} согласившимся**; "
        f"без согласия: {p['excluded_without_consent']}, в расчёт не вошли.",
        f"- Среди согласившихся хоть что-то делали на платформе: {p['with_activity']}; начали миссию: {p['started_a_mission']}; "
        f"завершили хотя бы одну: {p['finished_a_mission']}.",
        f"- Активны по неделям (от старых к новым): {', '.join(map(str, p['active_by_week']))}.",
        f"- Решено шагов: {s['solved']} ({_fmt(s['per_active_learner'])} на активного ученика). "
        f"Шагов, которые никто не открыл: {s['never_opened']} из {s['total']}.",
        f"- Есть след, но нет согласия: {p['activity_without_consent']} (в расчёты и в экспорт для исследования они не попадут).",
        "",
        "## Ключевые показатели",
        "",
        f"- Завершение миссий (MCR): **{_fmt(k['mission_completion_rate'], '%')}** "
        f"({k['missions_completed']} из {k['missions_started']}).",
        f"- Попыток до успеха (MAS): **{_fmt(k['mean_attempts_to_success'])}**.",
        f"- Отсев по шагам: **{_fmt(k['task_dropout_rate'], '%')}** ({k['steps_dropped']} из {k['steps_opened']}).",
        f"- Критический порог неудач подряд: **{_fmt(report['critical_threshold'])}**"
        f" (порог {report['metrics_meta']['critical_share']}% ушедших, выборка от {report['metrics_meta']['min_sample']}).",
        f"- Список раннего предупреждения сейчас: срочно {report['ews']['high']}, внимание {report['ews']['medium']}.",
        "",
        "| Неудач подряд | Дошли | Ушли |",
        "|---|---|---|",
    ]
    lines += [
        f"| {c['failures']} | {c['reached']} | {_fmt(c['dropout_rate'], '%')} |"
        for c in report["failure_curve"]
    ]
    lines += ["", "## Эксперимент с помощью после 3 неудач", ""]
    lines += [
        "Вмешательство — **баннер + бесплатная подсказка** (подсказка доступна только группе «баннер», "
        "см. `PILOT.md`): сравнение измеряет их вместе, эффект одного баннера отделить нельзя.",
        "",
    ]
    experiment = report["help_experiment"]
    if not experiment["arms"]:
        lines.append("Пока никто не дошёл до порога неудач.")
    else:
        lines += [
            "| Группа | Пар ученик×шаг | Решили | Ушли | Доп. попыток | Взяли помощь после | Из них бесплатная подсказка |",
            "|---|---|---|---|---|---|---|",
        ]
        for arm, a in sorted(experiment["arms"].items()):
            lines.append(
                f"| {'баннер + бесплатная подсказка' if arm == ARM_OFFER else 'контроль (без баннера и без бесплатной подсказки)'} | "
                f"{a['pairs']} | {a['solve_rate']}% | {a['dropout_rate']}% | {_fmt(a['extra_attempts'])} | "
                f"{a['helped_after_rate']}% | {a['rescued_after_rate']}% |"
            )
        comparison = experiment["comparison"]
        if comparison:
            for key, title in (("solved", "решили"), ("dropped", "ушли")):
                c = comparison[key]
                lines.append(
                    f"\nРазница «баннер + бесплатная подсказка» − «контроль», {title}: {c['diff'] * 100:+.1f} п.п., "
                    f"95% ДИ [{c['ci_low'] * 100:+.1f}; {c['ci_high'] * 100:+.1f}], p = {c['p_value']}."
                )
            if not comparison["enough"]:
                lines.append(
                    f"\n**Выборка мала** (меньше {MIN_ARM_SIZE} пар в группе): это наблюдение, а не доказательство."
                )
        else:
            lines.append("\nКонтрольной группы нет: `HELP_OFFER_SHARE` = 100 или в группе никого.")
    lines += ["", "## H3: ушли ли «срочные» чаще остальных", ""]
    h3 = report["h3"]
    if not h3["mature_days"]:
        lines.append(
            f"Пока нет снимков, у которых прошло окно наблюдения ({h3['window_days']} дн.). "
            "Снимки пишет `snapshot_early_warning` раз в сутки."
        )
    else:
        names = {"high": "срочно", "medium": "внимание", "ok": "остальные"}
        lines += [
            f"Ушёл = нет активности {h3['window_days']} дней после дня снимка; дней со снимками: {h3['mature_days']}.",
            "",
            "| Уровень | Строк (ученик×день) | Учеников | Ушли | Доля | 95% ДИ (по ученикам) |",
            "|---|---|---|---|---|---|",
        ]
        for level in ("high", "medium", "ok"):
            c = h3["levels"][level]
            lines.append(
                f"| {names[level]} | {c['rows']} | {c['learners']} | {c['left']} | {_fmt(c['share'], '%')} | "
                f"{'—' if c['ci_low'] is None else str(c['ci_low']) + '–' + str(c['ci_high']) + '%'} |"
            )
        lines.append(
            "\n"
            f"В списке (срочно + внимание) была доля ушедших **{_fmt(h3['listed']['share'], '%')}**, "
            f"среди всех **{_fmt(h3['all']['share'], '%')}**; доля ушедших, которых список заметил заранее: "
            f"{_fmt(h3['recall_listed'], '%')}. Дни одного ученика зависимы, поэтому интервал считается "
            "по числу учеников, а не строк."
        )
    sb = report["sandbox"]
    lines += ["", "## Здоровье песочницы (техническая метрика по всем запускам, без привязки к людям)", ""]
    if not sb["runs"]:
        lines.append("Запусков кода пока нет.")
    else:
        lines.append(
            f"- Запусков: {sb['runs']}; сбоев песочницы: **{sb['runner_error_rate']}%**; "
            f"таймаутов: {sb['timeout_rate']}%; превышений вывода: {sb['output_limit_rate']}%; "
            f"медиана времени: {sb['median_ms']} мс."
        )
        if sb["runner_error_rate"] > 2:
            lines.append("- **Сбоев больше 2%: разберитесь до того, как читать метрики** — они портят выборку.")
    lines += ["", "## Кабинет преподавателя: актуальность данных и удобство", ""]
    fresh, use = report["dashboard"]["freshness"], report["dashboard"]["usability"]
    if not fresh["samples"]:
        lines.append("- Актуальность данных: замеров нет (живой кабинет ещё не открывали при работающих учениках).")
    else:
        lines.append(
            f"- Актуальность данных: действие ученика доходит до панели в среднем за **{fresh['mean_s']} с** "
            f"(худшее {fresh['worst_s']} с, замеров {fresh['samples']}, действий {fresh['events']}); "
            f"в **{fresh['within_target_pct']}%** замеров самое медленное действие уложилось в {fresh['target_s']} с."
        )
    if not use["respondents"]:
        lines.append("- Удобство для преподавателя (SUS): ответов нет.")
    else:
        names = {"good": "хорошо", "average": "не хуже среднего", "below_average": "ниже среднего"}
        lines.append(
            f"- Удобство для преподавателя (SUS, 0–100): **{use['mean']}** "
            f"({names[use['verdict']]}; ориентир среднего {use['average_benchmark']}), "
            f"ответили {use['respondents']}, от {use['lowest']} до {use['highest']}."
        )
        if use["respondents"] < 5:
            lines.append("  Ответивших мало: это впечатление, а не оценка.")
    return "\n".join(lines) + "\n"
