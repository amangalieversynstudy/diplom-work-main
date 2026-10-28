"""The pilot's weekly report: who took part, how it is going, does help help.

Everything is computed from data the platform already stores. The numbers that go
into the thesis cover only learners who agreed to the research
(``Profile.research_consent``); the others are only counted, never analysed
(nothing personal is printed, only counts and rates).
"""

import math
from collections import Counter
from datetime import timedelta
from statistics import median
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from users.models import Profile

from .live import freshness_summary
from .snapshots import h3_summary
from .stats import effective_n
from .metrics import ABANDON_WINDOW_DAYS, _last_activity, compute_metrics, scoped_tasks
from .models import CodeRun, LearningEvent, MissionTask, Progress, TaskProgress
from .services import ARM_OFFER, HELP_AFTER_FAILURES, help_arm
from .usability import usability_summary
from .warning import assess_students

MIN_ARM_SIZE = 30  # below this the arm comparison is anecdote, not evidence
MIN_ARM_LEARNERS = 15  # ...and so is a comparison of pairs that come from fewer learners than this, per arm
WEEKS = 4

# the researcher sees every course, but the numbers come only from pilot content (see metrics.pilot_content_q)
_OWNER = SimpleNamespace(is_superuser=True, pilot_only=True)


def two_proportions(x1, n1, x2, n2, n_eff1=None, n_eff2=None):
    """Difference of two shares with a 95% interval and a two-sided p-value.

    Normal approximation: fine for hundreds of pairs, optimistic for dozens
    (the report says so). ``None`` if either group is empty.

    The shares are over (learner, step) pairs, but pairs of one learner are not independent. Pass the
    effective sample sizes ``n_eff1``/``n_eff2`` (``game.stats.effective_n`` of the rows per learner) to
    widen the interval and the p-value accordingly; without them every pair counts as independent.
    """
    if not n1 or not n2:
        return None
    p1, p2 = x1 / n1, x2 / n2
    diff = p1 - p2
    m1, m2 = n_eff1 or n1, n_eff2 or n2
    se = math.sqrt(p1 * (1 - p1) / m1 + p2 * (1 - p2) / m2)
    pooled = (x1 + x2) / (n1 + n2)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / m1 + 1 / m2))
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
    offered = LearningEvent.objects.filter(
        event_type=LearningEvent.HELP_OFFERED, task__in=scoped_tasks(_OWNER).values("pk")
    )
    if learner_ids is not None:
        offered = offered.filter(user_id__in=learner_ids)
    events = list(offered.values_list("user_id", "task_id", "created_at", "meta"))
    users = {user_id for user_id, *_ in events}
    last_seen = _last_activity(users)
    cutoff = now - timedelta(days=ABANDON_WINDOW_DAYS)
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
            arm,
            {
                "pairs": 0, "solved": 0, "dropped": 0, "extra": [], "helped": 0, "rescued": 0,
                "rows": Counter(), "known_rows": Counter(),
            },
        )
        bucket["pairs"] += 1
        bucket["solved"] += solved
        bucket["rows"][user_id] += 1
        if solved:
            bucket["extra"].append(max(0, row["attempts"] - HELP_AFTER_FAILURES))
            bucket["known_rows"][user_id] += 1
        elif last_seen.get(user_id, now - timedelta(days=3650)) < cutoff:
            bucket["dropped"] += 1
            bucket["known_rows"][user_id] += 1
        bucket["helped"] += any(t > stamp for t in helped_after.get((user_id, task_id), ()))
        bucket["rescued"] += any(t > stamp for t in rescued_after.get((user_id, task_id), ()))

    result = {}
    for arm, b in arms.items():
        pairs = b["pairs"]
        result[arm] = {
            "pairs": pairs,
            "learners": len(b["rows"]),
            "effective_pairs": round(effective_n(b["rows"]), 1),
            "effective_known_pairs": round(effective_n(b["known_rows"]), 1),
            "solved": b["solved"],
            "solve_rate": round(100 * b["solved"] / pairs, 1),
            "dropped": b["dropped"],
            # still active and unsolved: no outcome yet, not in the drop-out denominator
            "in_progress": pairs - b["solved"] - b["dropped"],
            "dropout_rate": (
                round(100 * b["dropped"] / (b["solved"] + b["dropped"]), 1)
                if b["solved"] + b["dropped"]
                else None
            ),
            "extra_attempts": round(sum(b["extra"]) / len(b["extra"]), 2) if b["extra"] else None,
            "helped_after_rate": round(100 * b["helped"] / pairs, 1),
            "rescued_after_rate": round(100 * b["rescued"] / pairs, 1),
        }
    offer, control = result.get(ARM_OFFER), result.get("control")
    comparison = None
    if offer and control:
        # the rows of one learner are one observation in the interval (see two_proportions)
        comparison = {
            "solved": two_proportions(
                offer["solved"], offer["pairs"], control["solved"], control["pairs"],
                offer["effective_pairs"], control["effective_pairs"],
            ),
            "dropped": two_proportions(
                offer["dropped"], offer["solved"] + offer["dropped"],
                control["dropped"], control["solved"] + control["dropped"],
                offer["effective_known_pairs"], control["effective_known_pairs"],
            ),
            "enough": (
                min(offer["pairs"], control["pairs"]) >= MIN_ARM_SIZE
                and min(offer["learners"], control["learners"]) >= MIN_ARM_LEARNERS
            ),
            "min_pairs": MIN_ARM_SIZE,
            "min_learners": MIN_ARM_LEARNERS,
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
    learners = get_user_model().objects.filter(is_staff=False, is_teacher=False)
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

    start = None
    if getattr(settings, "PILOT_STARTED_AT", ""):
        try:
            start = parse_datetime(settings.PILOT_STARTED_AT)
        except ValueError:
            start = None
        if start is not None and start.tzinfo is None:
            start = None
    metrics = compute_metrics(_OWNER, now=now, inactive_days=ABANDON_WINDOW_DAYS, consented_only=True)
    warnings = assess_students(_OWNER, now=now, consented_only=True)
    opened = {row["task_id"] for row in metrics["tasks"] if row["opened"]}
    all_steps = scoped_tasks(_OWNER).count()

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
        "performance": metrics["performance"],
        "behavioral_patterns": metrics["behavioral_patterns"],
        "failure_curve": metrics["failure_curve"],
        "critical_threshold": metrics["critical_threshold"],
        "critical_point": metrics["critical_point"],
        "threshold_status": metrics["threshold_status"],
        "ews": {
            "high": sum(a["level"] == "high" for a in warnings.values()),
            "medium": sum(a["level"] == "medium" for a in warnings.values()),
        },
        "help_experiment": help_experiment(now, learner_ids),
        "h3": h3_summary(now=now),
        "sandbox": sandbox_health(),
        "dashboard": {
            "freshness": freshness_summary(since=start),
            "usability": usability_summary(since=start),
            "since": start.isoformat() if start else None,
        },
        "metrics_meta": metrics["meta"],
    }


def _fmt(value, unit=""):
    return "—" if value is None else f"{value}{unit}"


def _threshold_text(report):
    """The H1 line: estimate and the lower bound of the interval apart, or "too little data"."""
    meta, point = report["metrics_meta"], report["critical_point"]
    need = f"нужно не меньше {meta['min_curve_pairs']} пар с известным исходом от {meta['min_curve_learners']} учеников"
    if report["threshold_status"] == "too_few":
        return f"мало данных ({need}), вывод не делаем"
    if point is None:
        return f"не найден: ни в одной точке с достаточной выборкой не ушло {meta['critical_share']}% и больше"
    verdict = (
        "нижняя граница интервала тоже не ниже порога" if point["confirmed"]
        else f"нижняя граница интервала ниже {meta['critical_share']}%, оценка предварительная"
    )
    return (
        f"{point['failures']} — ушли около {point['dropout_rate']}% "
        f"(95% ДИ {point['ci_low']}–{point['ci_high']}%, {point['learners']} учеников, "
        f"{point['known']} пар); {verdict}"
    )


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
        f"({k['missions_completed']} из {k['missions_started'] - k['missions_in_progress']} с известным исходом; "
        f"ещё в процессе: {k['missions_in_progress']}).",
        f"- Попыток до успеха (MAS): **{_fmt(k['mean_attempts_to_success'])}**.",
        f"- Сводный балл результативности (50% шаги + 30% звёзды + 20% объяснение): **{_fmt(k.get('performance_score'))}** (медиана {_fmt(k.get('performance_median'))}).",
        f"- Отсев по шагам: **{_fmt(k['task_dropout_rate'], '%')}** ({k['steps_dropped']} из {k['steps_known']} с известным исходом; ещё в процессе: {k['steps_in_progress']}).",
        f"- Критический порог неудач подряд: **{_threshold_text(report)}**",
        f"- Список раннего предупреждения сейчас: срочно {report['ews']['high']}, внимание {report['ews']['medium']}.",
        "",
        f"Ушёл = нет активности {report['metrics_meta']['inactive_days']} дней. "
        "Ученики, у которых окно ещё не прошло, в знаменатели не входят (колонка «в процессе»).",
        "",
        "| Неудач подряд | Дошли | Исход известен | В процессе | Учеников | Ушли | 95% ДИ (по ученикам) |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {c['failures']} | {c['reached']} | {c['known']} | {c['in_progress']} | {c['learners']} | "
        + (
            _fmt(c["dropout_rate"], "%") + " | " + f"{c['ci_low']}–{c['ci_high']}%"
            if c["enough"]
            else ("мало данных | —" if c["reached"] else "— | —")
        )
        + " |"
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
            "| Группа | Учеников | Пар ученик×шаг | Решили | Ушли (из тех, у кого исход известен) | Доп. попыток | Взяли помощь после | Из них бесплатная подсказка |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for arm, a in sorted(experiment["arms"].items()):
            lines.append(
                f"| {'баннер + бесплатная подсказка' if arm == ARM_OFFER else 'контроль (без баннера и без бесплатной подсказки)'} | "
                f"{a['learners']} | {a['pairs']} | {a['solve_rate']}% | {_fmt(a['dropout_rate'], '%')} | {_fmt(a['extra_attempts'])} | "
                f"{a['helped_after_rate']}% | {a['rescued_after_rate']}% |"
            )
        comparison = experiment["comparison"]
        if comparison and not comparison["enough"]:
            lines.append(
                f"\n**Мало данных** (в каждой группе нужно не меньше {comparison['min_pairs']} пар "
                f"и {comparison['min_learners']} учеников): разницу и p-value не показываем, "
                "таблица выше — наблюдение, а не вывод."
            )
        elif comparison:
            for key, title in (("solved", "решили"), ("dropped", "ушли")):
                c = comparison[key]
                lines.append(
                    f"\nРазница «баннер + бесплатная подсказка» − «контроль», {title}: {c['diff'] * 100:+.1f} п.п., "
                    f"95% ДИ [{c['ci_low'] * 100:+.1f}; {c['ci_high'] * 100:+.1f}], p = {c['p_value']}."
                )
            lines.append(
                "\nИнтервалы и p-value посчитаны с поправкой на кластеры: пары одного ученика считаются "
                "одним наблюдением (консервативно). Единица рандомизации — ученик."
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
    since = report["dashboard"].get("since")
    lines.append(
        "Учтены только преподаватели пилота (staff по коду приглашения, без самостоятельной регистрации)"
        + (f", с начала пилота {since}." if since else ".")
    )
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
        if use.get("excluded_respondents"):
            lines.append(f"  Ответы других аккаунтов не учтены: {use['excluded_respondents']}.")
        if use["respondents"] < 5:
            lines.append("  Ответивших мало: это впечатление, а не оценка.")
    return "\n".join(lines) + "\n"
