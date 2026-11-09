"""Is this deployment ready for a pilot with real students?

    python manage.py pilot_check

Every line is OK, WARN or FAIL. Any FAIL makes the command exit with an error,
so it can gate a deploy. WARN means "know what you are doing". Nothing here
changes any data.
"""

import os
from datetime import timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Q
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from game.models import Mission, MissionTask, Track

OK, WARN, FAIL = "OK", "WARN", "FAIL"
PUBLIC_JUDGE0 = "ce.judge0.com"


def docker_reachable():
    try:
        import docker

        docker.from_env(timeout=3).ping()
        return True
    except Exception:
        return False


def check_settings():
    """Yield ``(level, message)`` for the deployment's configuration."""
    if settings.DEBUG:
        yield FAIL, "DEBUG включён: в продакшене он должен быть выключен."
    else:
        yield OK, "DEBUG выключен."

    key = settings.SECRET_KEY
    if len(key) < 50 or key.startswith("django-insecure-"):
        yield FAIL, "SECRET_KEY короткий или сгенерирован Django: задайте длинный случайный."
    else:
        yield OK, "SECRET_KEY достаточно длинный."

    if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
        yield WARN, "База данных SQLite: для пилота нужен Postgres (иначе данные пропадут при деплое)."
    else:
        yield OK, "База данных не SQLite."

    if getattr(settings, "RUNNER_ALLOW_UNSAFE_FALLBACK", False):
        yield FAIL, "RUNNER_ALLOW_UNSAFE_FALLBACK=True: код учеников выполнялся бы на сервере приложения."
    else:
        yield OK, "Небезопасный запуск кода на сервере выключен."

    judge0 = (getattr(settings, "RUNNER_JUDGE0_URL", "") or "").strip()
    if docker_reachable():
        yield OK, "Docker-песочница доступна."
    elif judge0:
        yield OK, f"Код исполняет внешний Judge0 ({judge0})."
    else:
        yield FAIL, "Нет песочницы: ни Docker, ни RUNNER_JUDGE0_URL. Запуск кода работать не будет."
    if judge0 and PUBLIC_JUDGE0 in judge0:
        yield WARN, (
            "Используется публичный ce.judge0.com: код учеников уходит на стороннюю службу. "
            "Скажите об этом в согласии или поднимите свой Judge0."
        )

    if "console" in settings.EMAIL_BACKEND:
        yield WARN, "EMAIL_BACKEND=console: письма (подтверждение, сброс пароля) не уходят."
    else:
        yield OK, "Почтовый бэкенд настроен."

    invite = getattr(settings, "TEACHER_INVITE_CODE", "")
    if not invite:
        yield WARN, "TEACHER_INVITE_CODE выключен: преподавателя придётся создать через админку."
    elif "".join(c for c in str(invite).upper() if c.isalnum()) == "".join(
        c for c in str(getattr(settings, "TEACHER_INVITE_CODE_DEFAULT", "") or "").upper() if c.isalnum()
    ):
        yield WARN, "TEACHER_INVITE_CODE = публичный код пилота из репозитория: задайте свой на хостинге."
    else:
        yield OK, "TEACHER_INVITE_CODE задан: преподаватель регистрируется сам с этим кодом."

    mail_works = not settings.DEBUG and "console" not in getattr(settings, "EMAIL_BACKEND", "")
    if getattr(settings, "TEACHER_SELF_REGISTRATION", False) and not mail_works:
        yield WARN, (
            "Открытая регистрация преподавателей включена, а письма не уходят: преподаватели не подтверждают почту. "
            "Включайте её только вместе с RESEND_API_KEY и TEACHER_REQUIRE_EMAIL=1."
        )
    yield from check_period()

    if getattr(settings, "ANALYTICS_EXPORT_SALT", ""):
        yield OK, "ANALYTICS_EXPORT_SALT задан: псевдонимы в экспорте стабильны."
    else:
        yield WARN, "ANALYTICS_EXPORT_SALT пуст: псевдонимы строятся от SECRET_KEY и сломаются при его смене."

    days = getattr(settings, "LEARNING_DATA_RETENTION_DAYS", 0)
    if days:
        yield OK, f"Срок хранения данных: {days} дн. (не забудьте cron для prune_learning_data)."
    else:
        yield WARN, "LEARNING_DATA_RETENTION_DAYS не задан: срок хранения данных не ограничен."

    share = getattr(settings, "HELP_OFFER_SHARE", 100)
    if share >= 100:
        yield WARN, "HELP_OFFER_SHARE=100: контрольной группы нет, эффект баннера помощи измерить не получится."
    else:
        yield OK, f"Эксперимент с помощью: {share}% видят баннер, остальные контроль."

    if getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY"):
        yield WARN, (
            "AI-наставник (Мудрец) подключён: вопрос и код ученика уходят в Google Gemini. "
            "Скажите об этом в информационном листе."
        )
    else:
        yield WARN, (
            "GEMINI_API_KEY не задан: Мудрец недоступен, а баннер помощи после трёх неудач его предлагает. "
            "Ученики увидят «Мудрец сейчас недоступен»."
        )

    if getattr(settings, "RISK_MODEL_PATH", ""):
        yield WARN, (
            "Модель риска подключена (RISK_MODEL_PATH): во время пилота она меняет список «срочно», то есть само "
            "проверяемое правило H3. Держите переменную пустой до конца пилота."
        )
    else:
        yield OK, "Модель риска не подключена: список предупреждений работает по правилам (так и нужно до пилота)."

    if os.environ.get("ENABLE_STREAK_SCHEDULER") == "1":
        yield WARN, (
            "ENABLE_STREAK_SCHEDULER=1: кроме снимка, ученикам с почтой уходят письма о серии. Они удерживают "
            "учеников, поэтому держите их включёнными весь пилот и напишите о них в информационном листе "
            "(или снимайте снимок только через Railway Cron)."
        )

    if getattr(settings, "SOCIAL_ENABLED", True):
        yield WARN, (
            "Таверна включена (SOCIAL_ENABLED): обмен меняет запас подсказок (H2), а дуэли берут вопросы только "
            "из миссий, пройденных обоими. Решите до старта: выключить на время пилота "
            "(SOCIAL_ENABLED=0) или оставить всем и записать это в протокол."
        )
    else:
        yield OK, "Таверна выключена (SOCIAL_ENABLED=0): дуэли и обмен не влияют на данные пилота."


def check_period(now=None):
    """PILOT_STARTED_AT / PILOT_ENDED_AT: the format (a bare date is ignored silently) and yesterday's snapshot."""
    from game.cohort import parse_moment
    from game.models import EarlyWarningSnapshot

    raw_start = getattr(settings, "PILOT_STARTED_AT", "")
    raw_end = getattr(settings, "PILOT_ENDED_AT", "")
    start, end = parse_moment(raw_start), parse_moment(raw_end)
    example = "например 2026-11-09T00:00:00+05:00"
    if not raw_start:
        yield WARN, (
            "PILOT_STARTED_AT не задан: в исследование попадут все согласившиеся, включая тестовые аккаунты и "
            "репетицию, а в отчёт — SUS и замеры актуальности до старта. Задайте в день старта."
        )
    elif start is None:
        yield FAIL, f"PILOT_STARTED_AT={raw_start!r} не дата-время с часовым поясом ({example}): значение игнорируется."
    else:
        yield OK, f"Пилот идёт с {start.isoformat()}: в исследование входят ученики, зарегистрированные с этого момента."
    if raw_end and end is None:
        yield FAIL, f"PILOT_ENDED_AT={raw_end!r} не дата-время с часовым поясом ({example}): значение игнорируется."
    elif end is not None and start is not None and end <= start:
        yield FAIL, "PILOT_ENDED_AT не позже PILOT_STARTED_AT: проверьте даты."
    elif end is not None:
        yield OK, f"Активный период заканчивается {end.isoformat()}: после него снимки не пишутся, окна обрезаются."
    else:
        yield WARN, (
            "PILOT_ENDED_AT не задан: снимки и окна последних двух недель курса покажут «уход», которого не было. "
            "Задайте конец активного периода до старта."
        )

    now = now or timezone.now()
    running = start is not None and start <= now and (end is None or now < end)
    if running:
        yesterday = (now.astimezone(dt_timezone.utc) - timedelta(days=1)).date()
        if not EarlyWarningSnapshot.objects.filter(date=yesterday).exists():
            yield WARN, (
                f"Снимка списка за {yesterday} нет: этот день для H3 потерян. Проверьте Railway Cron "
                "snapshot_early_warning (нормально, только если вчера никто из участников ничего не делал)."
            )
        else:
            yield OK, f"Снимок списка за {yesterday} записан."


def _check_strength():
    """Hidden checks that never compare a call with a value, and stored checks that do not compile.

    The server itself compares ``assert power(3, 4) == 81`` (game.hidden_checks); a check made only of
    yes/no conditions (``assert isinstance(m, Hero)``) relies on what the sandbox reports.
    """
    from game.hidden_checks import compile_check
    from game.services import hidden_check_of
    from game.variants import personalize

    weak, broken = [], []
    for task in MissionTask.objects.filter(task_type="code", mission__is_active=True).order_by("pk"):
        check = hidden_check_of(personalize(task, None))
        if not check:
            continue
        try:
            if compile_check(check).weak:
                weak.append(task.pk)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            broken.append(task.pk)
    if broken:
        yield WARN, (
            f"Скрытая проверка не компилируется: {len(broken)} (id: {', '.join(map(str, broken))}). "
            "Такой шаг не пройти никому: исправьте проверку в Studio."
        )
    if weak:
        yield WARN, (
            f"Скрытых проверок только из условий «да/нет»: {len(weak)} (id: {', '.join(map(str, weak))}). "
            "Добавьте сравнение вызова со значением, например assert power(3, 4) == 81: его сервер проверяет сам."
        )


def check_data():
    """Yield ``(level, message)`` for migrations, the course and the teachers."""
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if pending:
        yield FAIL, f"Не применено миграций: {len(pending)}. Выполните migrate."
    else:
        yield OK, "Все миграции применены."

    tracks = list(Track.objects.filter(is_active=True))
    playable = Mission.objects.filter(is_active=True, tasks__isnull=False).distinct().count()
    if not tracks or not playable:
        yield FAIL, "Нет опубликованного курса с миссиями: выполните seed_course."
    else:
        yield OK, f"Опубликовано курсов: {len(tracks)}, миссий с заданиями: {playable}."
    empty = MissionTask.objects.filter(task_type="quiz", data={}).count()
    if empty:
        yield WARN, f"Квизов без данных (ответ не проверить): {empty}."

    unchecked = [
        task.pk
        for task in MissionTask.objects.filter(task_type="code", mission__is_active=True)
        if isinstance(task.data, dict)
        and task.data.get("expected_output")
        and not task.data.get("hidden_check")
    ]
    if unchecked:
        yield WARN, (
            f"Кодовых шагов без скрытой проверки: {len(unchecked)} (id: {', '.join(map(str, unchecked))}). "
            "Их можно пройти, просто напечатав ответ, и MAS по ним занижен. Добавьте проверку в Studio."
        )
    else:
        yield OK, "У всех кодовых шагов с эталонным выводом есть скрытая проверка."
    yield from _check_strength()

    # the built-in steps that came with "not taught yet" lists and personal variants later
    from game.management.commands.sync_course_protection import PROTECTION_KEYS, protected_steps

    present = MissionTask.objects.in_bulk(list(protected_steps()))
    bare = [
        pk
        for pk, step in present.items()
        if not any(key in (step.data or {}) for key in PROTECTION_KEYS)
    ]
    from game.management.commands.sync_course_protection import explain_steps

    missing_explain = [
        pk
        for pk, fields in explain_steps().items()
        if not MissionTask.objects.filter(pk=pk).exists() and Mission.objects.filter(pk=fields["mission"]).exists()
    ]
    if missing_explain:
        bare = bare or missing_explain
    if bare:
        yield WARN, (
            "У встроенных кодовых шагов нет персональных вариантов, списков «не проходили» или вопроса "
            "«объясни своё решение» (база развёрнута до их появления): выполните sync_course_protection."
        )

    User = get_user_model()
    if not User.objects.filter(Q(is_staff=True) | Q(is_teacher=True), is_active=True).exists():
        yield FAIL, "Нет ни одного преподавателя (staff): некому смотреть аналитику."
    if not User.objects.filter(is_staff=True, is_superuser=False, is_teacher=False, is_active=True).exists():
        yield WARN, (
            "Нет преподавателя пилота (staff по коду приглашения): SUS и актуальность данных в отчёт берутся "
            "только от них, раздел будет пустым."
        )
    unvetted_public = list(
        Track.objects.filter(is_public=True, owner__isnull=False, owner__is_superuser=False)
        .filter(Q(owner__is_staff=False) | Q(owner__is_teacher=True))
        .values_list("slug", flat=True)
    )
    if unvetted_public:
        yield WARN, (
            "Публичные курсы у преподавателей без доверия: " + ", ".join(unvetted_public)
            + ". Их владельцы видели бы всех учеников курса: сделайте курсы закрытыми (миграция 0021 делает это)."
        )
    homeless = [t.slug for t in tracks if t.owner_id is None]
    if homeless and not User.objects.filter(is_superuser=True, is_active=True).exists():
        yield FAIL, f"Курсы без владельца ({', '.join(homeless)}) и нет суперпользователя: аналитика будет пустой."
    elif homeless:
        yield WARN, (
            f"Курсы без владельца: {', '.join(homeless)}. Преподаватель без прав суперпользователя "
            "не увидит их учеников: выполните set_course_owner."
        )
    elif tracks:
        yield OK, "У всех курсов есть владелец."

    from game.management.commands.seed_demo_cohort import demo_users

    demo = demo_users().count()
    if demo:
        yield WARN, (
            f"В базе {demo} демонстрационных учеников (demo_*): их цифры попадут в кабинет и рейтинг. "
            "Перед пилотом уберите их: seed_demo_cohort --remove."
        )

    from game.cohort import pilot_learners, research_learners

    cohort = pilot_learners().count()
    agreed = research_learners().count()
    share = f" ({round(100 * agreed / cohort)}%)" if cohort else ""
    yield (OK if not cohort or agreed / cohort >= 0.8 else WARN), (
        f"Согласились на исследование: {agreed} из {cohort} учеников пилотной когорты{share}; цель — 80% и выше."
    )


class Command(BaseCommand):
    help = "Check that the deployment is ready for a pilot with real students."

    def handle(self, *args, **options):
        failures = 0
        for level, message in (*check_settings(), *check_data()):
            style = {OK: self.style.SUCCESS, WARN: self.style.WARNING, FAIL: self.style.ERROR}[level]
            self.stdout.write(style(f"[{level:>4}] {message}"))
            failures += level == FAIL
        if failures:
            raise CommandError(f"Не готово к пилоту: проблем {failures}.")
        self.stdout.write(self.style.SUCCESS("Проверка пройдена (предупреждения читать обязательно)."))
