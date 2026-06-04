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

# Vercel rotates the preview subdomain hash on every deploy, so pinning a single
# origin is brittle. Match this project's Vercel URLs by regex instead — scoped
# to the project name so arbitrary *.vercel.app sites are NOT allowed.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://diplom-work-main-[a-z0-9-]+\.vercel\.app$",
    r"^https://diplom-work-main\.vercel\.app$",
]
CORS_ALLOWED_ORIGIN_REGEXES += [
    r.strip()
    for r in os.getenv("CORS_ALLOWED_ORIGIN_REGEXES", "").split(",")
    if r.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ─── Teacher self-registration (invite code) ──────────────────────────────
# Ship a working default so teacher sign-up works in prod out of the box —
# no one has to set a Railway variable first. Teachers register at /register
# with this code and get is_staff (cabinet + analytics). Setting the
# TEACHER_INVITE_CODE env var overrides this, so the code can be rotated
# without a redeploy. (base.py defaults to "" = disabled; this opts prod in,
# exactly like local.py does for dev.)
TEACHER_INVITE_CODE = TEACHER_INVITE_CODE or "RPG-TEACHER-2026"

# ─── code runner on Docker-less hosts (Railway) ───────────────────────────
# Primary path here is the external Judge0 sandbox (RUNNER_JUDGE0_URL, inherited
# from base) — code runs OFF this server, so app secrets/filesystem stay safe.
# The local subprocess fallback only triggers if Judge0 is unreachable; it is
# now hardened (scrubbed env without secrets, CPU/mem/proc rlimits, own session
# + process-group kill, temp cwd). We keep it ENABLED so a live demo still works
# if Judge0 is briefly down. Set RUNNER_ALLOW_UNSAFE_FALLBACK=False to force
# Judge0-only (no local execution).
RUNNER_ALLOW_UNSAFE_FALLBACK = os.getenv(
    "RUNNER_ALLOW_UNSAFE_FALLBACK", "True"
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
