"""Is this deployment ready for a pilot with real students?

    python manage.py pilot_check

Every line is OK, WARN or FAIL. Any FAIL makes the command exit with an error,
so it can gate a deploy. WARN means "know what you are doing". Nothing here
changes any data.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from game.models import Mission, MissionTask, Track
from users.models import Profile

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

    if getattr(settings, "TEACHER_INVITE_CODE", ""):
        yield OK, "TEACHER_INVITE_CODE задан: преподаватель может зарегистрироваться сам."
    else:
        yield WARN, "TEACHER_INVITE_CODE пуст: преподавателя придётся создать через админку."

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

    yield OK, (
        "Модель риска подключена." if getattr(settings, "RISK_MODEL_PATH", "")
        else "Модель риска не подключена: список предупреждений работает по правилам (так и нужно до пилота)."
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

    User = get_user_model()
    if not User.objects.filter(is_staff=True, is_active=True).exists():
        yield FAIL, "Нет ни одного преподавателя (staff): некому смотреть аналитику."
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

    yield OK, (
        f"Согласились на исследование: {Profile.objects.filter(research_consent=True).count()} "
        f"из {Profile.objects.filter(user__is_staff=False).count()} учеников."
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
