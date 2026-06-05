"""Django AppConfig for the game application."""

from django.apps import AppConfig


class GameConfig(AppConfig):
    """Configuration for the game app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "game"

    def ready(self):
        # подключаем signals для leaderboard updates
        from . import signals  # noqa: F401

        # Ежедневное email-напоминание о стрике без отдельного Railway-сервиса:
        # планировщик живёт внутри web-процесса. Включается переменной
        # ENABLE_STREAK_SCHEDULER=1, чтобы не стартовать в тестах/миграциях.
        import os

        if os.environ.get("ENABLE_STREAK_SCHEDULER") == "1":
            from . import scheduler

            scheduler.start()
