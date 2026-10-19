"""DRF exception handler: a rate limit from django-ratelimit is a 429, not a 403 "permission denied"."""

from django_ratelimit.exceptions import Ratelimited
from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    if isinstance(exc, Ratelimited):
        exc = Throttled(detail="Слишком много попыток. Подождите минуту и попробуйте снова.")
    return exception_handler(exc, context)
