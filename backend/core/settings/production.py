"""Production Django settings for deployment."""

import logging

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Cloudflare Tunnel / nginx ставят запрос как https, но к Daphne приходит http.
# Это говорит Django доверять заголовку X-Forwarded-Proto от прокси.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Список доменов, с которых разрешён POST/PUT/DELETE (нужно для cloudflared/ngrok/nginx).
# Пример .env: CSRF_TRUSTED_ORIGINS="https://*.trycloudflare.com,https://*.duckdns.org,https://my-domain.ru"
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "https://*.trycloudflare.com,https://*.duckdns.org,https://*.loca.lt",
).split(",")

# ─── MID-04: Security headers ─────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# HSTS — 1 год + subdomains + preload-ready
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies только по HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ─── CRIT-02: Email backend для production ────────────────────────────────
# По умолчанию base.py = console (письма в логи). В проде ОБЯЗАТЕЛЬНО
# переопределить через env:
#   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
#   EMAIL_HOST=smtp.gmail.com  (или sendgrid/ses/mailgun)
#   EMAIL_HOST_USER=...
#   EMAIL_HOST_PASSWORD=...
_logger = logging.getLogger(__name__)
if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":  # noqa: F405
    _logger.warning(
        "[PRODUCTION] EMAIL_BACKEND == console — верификационные письма "
        "не уходят на реальный SMTP. Установи переменные EMAIL_* в .env.prod."
    )

# ─── MID-01: Sentry (опционально, включается переменной SENTRY_DSN) ──────
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        )
    except ImportError:
        _logger.warning(
            "[PRODUCTION] SENTRY_DSN указан, но sentry-sdk не установлен. "
            "Добавь sentry-sdk в requirements.txt."
        )
