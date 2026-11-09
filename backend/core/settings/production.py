"""Production Django settings for deployment."""

import logging
import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

# One trusted proxy hop (the Railway edge) in front of daphne: throttles and rate limits key on the right-most
# X-Forwarded-For entry, which the client cannot forge. Put another proxy in front (Cloudflare) -> NUM_PROXIES=2.
REST_FRAMEWORK["NUM_PROXIES"] = int(os.getenv("NUM_PROXIES", "1"))  # noqa: F405

DEBUG = False
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"  # noqa: F405

# ─── ALLOWED_HOSTS: no wildcard default ────────────────────────────────────
# The same list is used by Channels' AllowedHostsOriginValidator (core/asgi.py),
# so a WebSocket from a foreign Origin is refused too. Railway exposes the
# service domain as RAILWAY_PUBLIC_DOMAIN; it is added automatically.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_domain and _railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_domain)
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must list the real hosts in production (no empty value, no '*'). "
        "Set the ALLOWED_HOSTS variable, e.g. ALLOWED_HOSTS=api.example.com,"
        "myapp.up.railway.app (Railway also provides RAILWAY_PUBLIC_DOMAIN)."
    )
# Railway's health check calls /healthz with this Host header (a DisallowedHost would fail every deploy)
if os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("RAILWAY_PROJECT_ID"):
    ALLOWED_HOSTS.append("healthcheck.railway.app")

# ─── CRIT: SECRET_KEY must be set explicitly in production ─────────────────
# base.py falls back to the insecure literal "dev-secret"; refuse to boot prod
# with it so sessions/JWTs cannot be forged with a public, predictable key.
if os.getenv("DJANGO_SECRET_KEY", "") in ("", "dev-secret"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong, unique value in production. "
        "Set it as a Railway/host environment variable."
    )

# ─── CRIT: CORS — never allow all origins in production ───────────────────
# Exact frontend origins only. No pattern over *.vercel.app can be safe: anybody can name their own Vercel
# project "diplom-work-main-<anything>" (or end the name with this team's slug) and get an address that
# matches. The live site is listed by default; FRONTEND_URL (also used for e-mail links) and
# CORS_ALLOWED_ORIGINS add more. A preview deployment that has to call the API is added the same way, by
# its exact address (CORS_ALLOWED_ORIGIN_REGEXES is still read from the environment as a last resort).
CORS_ALLOW_ALL_ORIGINS = False
DEFAULT_FRONTEND_ORIGINS = ["https://diplom-work-main-frontend.vercel.app"]
_frontend_origin = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
CORS_ALLOWED_ORIGINS = list(
    dict.fromkeys(
        DEFAULT_FRONTEND_ORIGINS
        + ([_frontend_origin] if _frontend_origin else [])
        + [o.strip().rstrip("/") for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    )
)
# The code runner's WebSocket is checked by its Origin against ALLOWED_HOSTS (core/asgi.py): the frontend's own
# host has to be there, or every run from the site is refused. Taken from the origins above, no second variable.
for _origin in CORS_ALLOWED_ORIGINS:
    _origin_host = urlsplit(_origin).hostname
    if _origin_host and _origin_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_origin_host)

CORS_ALLOWED_ORIGIN_REGEXES = [
    r.strip()
    for r in os.getenv("CORS_ALLOWED_ORIGIN_REGEXES", "").split(",")
    if r.strip()
]
# The site sends its JWT in the Authorization header and uses no cookies across origins, so credentialed CORS
# stays off: a page on another origin can never ride a logged-in admin's session cookie.
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "0").strip().lower() in ("1", "true", "yes", "on")

# ─── Teacher sign-up (invite code) ────────────────────────────────────────
# The invite code (base.py) gives only the self-service teacher role: own closed courses, only their own classes'
# learners, no admin, no global rewards from their classes. The default (PILOT-2026) is public, it is in the
# repository, so in production it switches the invite OFF instead of letting anybody in: set
# TEACHER_INVITE_CODE to your own value on the host (rotate it by changing the variable). Vetted teachers
# (public courses) are still made by hand in the admin.
_norm_code = lambda s: "".join(c for c in (s or "").upper() if c.isalnum())  # noqa: E731
if TEACHER_INVITE_CODE and _norm_code(TEACHER_INVITE_CODE) == _norm_code(TEACHER_INVITE_CODE_DEFAULT):  # noqa: F405
    TEACHER_INVITE_CODE = ""
    logging.getLogger(__name__).warning(
        "[PRODUCTION] TEACHER_INVITE_CODE is the public default from the repository, so the teacher invite is OFF:"
        " set your own value on the host to switch it on."
    )

# Open teacher sign-up (no code at all) is OFF in production until it is switched on on purpose: set
# TEACHER_SELF_REGISTRATION=1 only together with real e-mail and TEACHER_REQUIRE_EMAIL=1.
TEACHER_SELF_REGISTRATION = os.getenv("TEACHER_SELF_REGISTRATION", "0").strip().lower() in ("1", "true", "yes", "on")

# ─── code runner on Docker-less hosts (Railway) ───────────────────────────
# Primary path here is the external Judge0 sandbox (RUNNER_JUDGE0_URL, inherited
# from base) - code runs OFF this server, so app secrets/filesystem stay safe.
# The local subprocess fallback runs student code on THIS server without real
# isolation, so it is OFF in production: if Judge0 is down the student gets a
# clear "sandbox unavailable" message instead of remote code execution.
# Only set RUNNER_ALLOW_UNSAFE_FALLBACK=True for a throwaway demo, never with
# real user data or secrets on the host.
RUNNER_ALLOW_UNSAFE_FALLBACK = os.getenv(
    "RUNNER_ALLOW_UNSAFE_FALLBACK", "False"
).lower() in {"1", "true", "yes", "on"}

# Cloudflare Tunnel / nginx ставят запрос как https, но к Daphne приходит http.
# Это говорит Django доверять заголовку X-Forwarded-Proto от прокси.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Домены, с которых разрешены POST/PUT/DELETE. Только из переменной окружения,
# без умолчаний для публичных туннелей.
# Пример: CSRF_TRUSTED_ORIGINS="https://my-app.vercel.app,https://api.example.com"
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# Редирект http -> https (за прокси Railway). Отключается только переменной.
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in {"1", "true", "yes", "on"}
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]

# ─── Security headers ─────────────────────────────────────────────
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

# ─── Email backend для production ────────────────────────────────
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

# ─── Sentry (опционально, включается переменной SENTRY_DSN) ──────
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
