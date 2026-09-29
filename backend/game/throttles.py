"""DRF throttle-классы для защиты дорогих эндпоинтов.

AI-помощник (Gemini) — квота на токены и стоимость.
Code Runner (Docker sandbox) — ресурсоёмкий запуск контейнеров.
Burst-лимит защищает от спам-кликов "Run" в редакторе.

DRF "из коробки" умеет периоды только в формате <num>/<s|m|h|d>. Для
burst-лимита нужен интервал в N секунд — поэтому здесь кастомный
parse_rate(), который поддерживает синтаксис вида "5/10s" → 5 запросов
за 10 секунд.
"""

from django.core.cache import cache
from rest_framework.throttling import UserRateThrottle


class _CustomPeriodThrottle(UserRateThrottle):
    """UserRateThrottle с расширенным parse_rate.

    Поддерживает форматы:
        "5/s", "5/min", "5/h", "5/d" — как у DRF
        "5/10s", "20/5m" — N запросов за <число><единица>
    """

    _UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        num, period = rate.split("/")
        num_requests = int(num)
        # период может быть "s", "min", "10s", "2m" и т.п.
        # отрезаем цифры С НАЧАЛА строки и берём первую букву как unit
        unit_part = period.lstrip("0123456789") or "s"
        unit = unit_part[0]
        multiplier_str = period[: len(period) - len(unit_part)] or "1"
        multiplier = int(multiplier_str) if multiplier_str.isdigit() else 1
        duration = self._UNITS[unit] * multiplier
        return (num_requests, duration)


class AIAssistThrottle(UserRateThrottle):
    """Gemini: дорого по API-квоте. 10 запросов/мин на юзера."""

    scope = "ai_assist"


class TaskSubmitThrottle(UserRateThrottle):
    """Answer submissions (quiz/story): stops brute-forcing quiz options."""

    scope = "task_submit"


class LearningEventThrottle(UserRateThrottle):
    """Client-reported timeline events (e.g. a step was opened)."""

    scope = "learning_event"


class CodeRunnerThrottle(UserRateThrottle):
    """Docker sandbox: ресурсоёмко. 20 запусков/мин на юзера."""

    scope = "code_runner"


class CodeRunnerBurstThrottle(_CustomPeriodThrottle):
    """Защита от спам-кликов кнопки Run: 5 запусков за 10 секунд.

    Использует кастомный parse_rate, поэтому понимает period "10s".
    """

    scope = "code_runner_burst"


# ── WebSocket runner limits ─────────────────────────────────────────────────
# DRF throttles only see HTTP, so the WebSocket runner counts runs itself, per
# user, in the shared cache (Redis in production). Same numbers as the REST
# runner: 5 runs per 10 seconds and 20 per minute.

RUNNER_LIMITS = (("burst", 5, 10), ("minute", 20, 60))


def _within_limit(key, limit, window_seconds):
    """Count one hit in a fixed window; False once *limit* is exceeded."""
    if cache.add(key, 1, window_seconds):
        return limit >= 1
    try:
        return cache.incr(key) <= limit
    except ValueError:  # the window expired between add() and incr()
        cache.set(key, 1, window_seconds)
        return True


def allow_code_run(user_id):
    """Register a run for *user_id*; False if they are running code too fast."""
    return all(
        _within_limit(f"runner:{user_id}:{name}", limit, window)
        for name, limit, window in RUNNER_LIMITS
    )
