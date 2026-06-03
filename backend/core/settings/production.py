"""Production Django settings for deployment."""

import logging

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# ─── CRIT: SECRET_KEY must be set explicitly in production ─────────────────
# base.py falls back to the insecure literal "dev-secret"; refuse to boot prod
# with it so sessions/JWTs cannot be forged with a public, predictable key.
if os.getenv("DJANGO_SECRET_KEY", "") in ("", "dev-secret"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong, unique value in production. "
        "Set it as a Railway/host environment variable."
    )

# ─── CRIT: CORS — never allow all origins in production ───────────────────
# Lock the API down to the known frontend origin(s). Falls back to FRONTEND_URL
# (already configured for email links) so an existing deployment keeps working.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
_frontend_origin = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if not CORS_ALLOWED_ORIGINS and _frontend_origin:
    CORS_ALLOWED_ORIGINS = [_frontend_origin]
CORS_ALLOW_CREDENTIALS = True

# ─── CRIT: code runner — forbid the unsandboxed subprocess fallback ───────
# On hosts without Docker (e.g. Railway) the runner would otherwise execute
# arbitrary user Python directly in the app process. Disallow that here; the
# Docker-sandboxed path still works wherever Docker is available.
RUNNER_ALLOW_UNSAFE_FALLBACK = os.getenv(
    "RUNNER_ALLOW_UNSAFE_FALLBACK", "False"
).lower() in {"1", "true", "yes", "on"}

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
