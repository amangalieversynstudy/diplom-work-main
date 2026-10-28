"""Base Django settings for the backend project."""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")

# Gemini AI — set in .env or environment; leave empty to disable AI hints
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Code runner execution backends, in priority order:
#   1) Docker sandbox — used wherever a Docker daemon is reachable;
#   2) Judge0 — external sandbox API (ce.judge0.com), used when Docker is absent
#      (e.g. Railway). Code runs OFF our server, so app secrets/FS stay safe.
#      The public instance works keyless; set RUNNER_JUDGE0_KEY (RapidAPI) or
#      RUNNER_JUDGE0_URL (self-hosted) for a more reliable/private endpoint;
#   3) local subprocess fallback — hardened (scrubbed env, rlimits, own session,
#      temp cwd) but NOT a true sandbox; gated by RUNNER_ALLOW_UNSAFE_FALLBACK,
#      which is OFF by default (only local.py switches it on for development).
# Set RUNNER_JUDGE0_URL="" to disable the Judge0 hop (tests do this to stay offline).
RUNNER_JUDGE0_URL = os.getenv("RUNNER_JUDGE0_URL", "https://ce.judge0.com")
RUNNER_JUDGE0_KEY = os.getenv("RUNNER_JUDGE0_KEY", "")
RUNNER_JUDGE0_HOST = os.getenv("RUNNER_JUDGE0_HOST", "judge0-ce.p.rapidapi.com")
# 100 = Python 3.12 on ce.judge0.com (71 is Python 3.8, older than the courses and the local runner)
RUNNER_JUDGE0_LANGUAGE_ID = int(os.getenv("RUNNER_JUDGE0_LANGUAGE_ID", "100"))

RUNNER_ALLOW_UNSAFE_FALLBACK = os.getenv(
    "RUNNER_ALLOW_UNSAFE_FALLBACK", "False"
).lower() in {"1", "true", "yes", "on"}

# Frontend URL — used in email verification links
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Django admin login without ?next lands on the admin (API auth is JWT, not session).
LOGIN_REDIRECT_URL = "/admin/"

# Teacher invite code for the pilot: given at sign-up (the «Код преподавателя» field) or later in the profile
# («Активировать доступ преподавателя»), it grants the self-service teacher role (is_teacher): own courses and
# classes only, never the admin, never other teachers' learners. Vetting (is_staff) stays a manual act in the admin.
# Unset = the pilot default below; "off" (or 0/false/no) switches the code off. Set your own value on the host:
# this default is in a public repository.
TEACHER_INVITE_CODE_DEFAULT = "PILOT-2026"
_invite_code = os.getenv("TEACHER_INVITE_CODE")
if _invite_code is None:
    TEACHER_INVITE_CODE = TEACHER_INVITE_CODE_DEFAULT
elif _invite_code.strip().lower() in ("", "off", "0", "false", "no"):
    TEACHER_INVITE_CODE = ""
else:
    TEACHER_INVITE_CODE = _invite_code.strip()
# Self-service teacher role at sign-up (the "I am a teacher" choice). Switch it off with
# TEACHER_SELF_REGISTRATION=0 and a teacher can only join with the invite code above.
TEACHER_SELF_REGISTRATION = os.getenv("TEACHER_SELF_REGISTRATION", "1").strip().lower() in ("1", "true", "yes", "on")
# A self-service teacher must give an e-mail and confirm it before the cabinet opens. Applies only when e-mail
# really goes out (not DEBUG, not the console backend), so teachers are never locked out by a missing mail setup.
TEACHER_REQUIRE_EMAIL = os.getenv("TEACHER_REQUIRE_EMAIL", "0").strip().lower() in ("1", "true", "yes", "on")

# Studio size limits for teachers who are not superusers (env-tunable). The built-in courses have 1 section,
# 8 missions and at most 4 steps a mission, so every cap stays well above them.
STUDIO_LIMITS = {
    "tracks_per_teacher": int(os.getenv("STUDIO_TRACKS_PER_TEACHER", "10")),
    "tracks_per_vetted_teacher": int(os.getenv("STUDIO_TRACKS_PER_VETTED_TEACHER", "50")),
    "sections_per_track": int(os.getenv("STUDIO_SECTIONS_PER_TRACK", "20")),
    "missions_per_track": int(os.getenv("STUDIO_MISSIONS_PER_TRACK", "60")),
    "tasks_per_mission": int(os.getenv("STUDIO_TASKS_PER_MISSION", "20")),
}

# Start of the pilot (ISO date-time with a time zone, e.g. 2026-11-02T00:00:00+05:00). The pilot report's teacher
# measurements (SUS, data freshness) count only what was recorded from then on; empty = everything.
PILOT_STARTED_AT = os.getenv("PILOT_STARTED_AT", "")

# Debug flag (enable via env DEBUG=True/False)
DEBUG = os.getenv("DEBUG", "True").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")

INSTALLED_APPS = [
    # daphne must come first so it overrides runserver with the ASGI server,
    # ensuring WebSocket support during `manage.py runserver`.
    "daphne",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_yasg",
    "anymail",
    "users",
    "game",
]

# Use custom user model
AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# Channels: in-memory layer is sufficient for the single-process Daphne
# deployment. If we ever scale to multiple worker processes, switch to
# ``channels_redis.core.RedisChannelLayer`` with the existing REDIS_URL.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

_DATABASE_URL = os.getenv("DATABASE_URL")
if _DATABASE_URL:
    import dj_database_url
    # Under ASGI (Daphne) every request runs its sync code in its own thread, so Django's docs advise against
    # persistent connections there; each idle one also costs Postgres RAM. 0 = a connection per request.
    DATABASES = {
        "default": dj_database_url.parse(
            _DATABASE_URL, conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "0")), conn_health_checks=True
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "rpgdb"),
            "USER": os.getenv("POSTGRES_USER", "rpguser"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "rpgpass"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# WhiteNoise: enable gzip and immutable file headers
# WhiteNoise storage:
if DEBUG:
    # в dev избегаем manifest-сториджа, чтобы не падать на collectstatic до наличия манифеста
    _STATIC_BACKEND = "whitenoise.storage.CompressedStaticFilesStorage"
else:
    _STATIC_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": _STATIC_BACKEND},
}

# django-ratelimit uses the same client address as the DRF throttles (see core/client_ip.py)
RATELIMIT_IP_META_KEY = "core.client_ip.client_ip"

REST_FRAMEWORK = {
    # a django-ratelimit limit answers 429 like a DRF throttle, not 403
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    # JWT auth for API
    # JWT plus the teacher's «Глазами студента» switch (the X-View-As header, see core/authentication.py)
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.authentication.ViewAsJWTAuthentication",
    ),
    # Secure by default: an endpoint is closed to anonymous users unless it
    # explicitly declares AllowAny (registration, login, public catalogue...).
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # Always return JSON for API (avoid HTML browsable API in load tests)
    "DEFAULT_RENDERER_CLASSES": (
        [
            "rest_framework.renderers.JSONRenderer",
            "rest_framework.renderers.BrowsableAPIRenderer",
        ]
        if DEBUG
        else ["rest_framework.renderers.JSONRenderer"]
    ),
    # Accept JSON and form-encoded payloads by default
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    # Throttling — глобальные классы плюс named scopes для AI и Runner
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "120/min",
        "ai_assist": "10/min",        # Gemini — дорого
        "task_submit": "60/min",       # ответы на квизы/сюжет
        "usability_submit": "5/day",   # анкета SUS
        "class_join": "20/hour",       # вход в класс по коду: нельзя подбирать коды
        "class_join_ip": "150/hour",   # то же с одного адреса (класс за одним NAT укладывается)
        "teacher_analytics": "30/min", # тяжёлые отчёты преподавателя (кабинет, метрики, CSV)
        "teacher_live": "20/min",      # живая панель опрашивает раз в 10 с
        "studio_write": "60/min",      # правки Студии
        "studio_write_day": "1000/day",
        "mission_complete": "20/min",  # завершение миссии
        "learning_event": "120/min",   # события UI (открытие шага)
        "code_runner": "20/min",       # Docker sandbox — ресурсоёмко
        "code_runner_burst": "5/10s",  # Защита от спам-кликов Run
        "teacher_code": "10/hour",     # код преподавателя в профиле: подбирать нельзя
    },
}

# Learning-analytics footprint: how long code runs / events are kept, and the
# secret that turns user ids into pseudonyms in exports (falls back to
# SECRET_KEY when empty). See game/management/commands/export_learning_data.py.
LEARNING_DATA_RETENTION_DAYS = int(os.getenv("LEARNING_DATA_RETENTION_DAYS", "730"))
ANALYTICS_EXPORT_SALT = os.getenv("ANALYTICS_EXPORT_SALT", "")
# Optional drop-out risk model (JSON from ml/risk/train.py); empty = rules only.
RISK_MODEL_PATH = os.getenv("RISK_MODEL_PATH", "")
# Share (0-100) of learners who see the "help after 3 failures" banner. The rest
# are a control group that keeps the normal hint/AI tools but gets no prompt;
# 100 = everyone (no experiment). Used for the pilot, see docs/PILOT.md.
HELP_OFFER_SHARE = int(os.getenv("HELP_OFFER_SHARE", "100"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

CORS_ALLOW_ALL_ORIGINS = True
# the frontend on another domain (Vercel) sends the «Глазами студента» header: the preflight must allow it
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = (*default_headers, "x-view-as")

# Cache for the throttles, rate limits and the live panel. With REDIS_URL it is Redis (counters shared by several
# processes or replicas); without it, the memory of the one Daphne process. That is exact for a single process
# (the Railway Hobby setup: one service, no Redis to pay for); the counters only reset on a restart.
_REDIS_URL = os.getenv("REDIS_URL", "").strip()
if _REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": _REDIS_URL}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "rpg-academy"}}

# Email for dev (console) - change in production
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ("true", "1", "yes")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
# Hard 10-second timeout — без него smtplib может висеть до 60с и убивать gunicorn worker.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

# Resend (HTTP API) — Railway блокирует SMTP, поэтому шлём через HTTPS API.
# Включается установкой RESEND_API_KEY в env. EMAIL_BACKEND автоматически
# переключается на anymail.backends.resend.EmailBackend.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
if RESEND_API_KEY:
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {"RESEND_API_KEY": RESEND_API_KEY}

# Public URL of the frontend (used in verification links inside emails)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# drf-yasg: silence compat renderer deprecation
SWAGGER_USE_COMPAT_RENDERERS = False

# ── Jazzmin: брендированная админка под стиль RPG Academy ───────────────────
# CMS для руководителей курсов: правка Track → Location → Mission → MissionTask.
JAZZMIN_SETTINGS = {
    "site_title": "RPG Academy",
    "site_header": "RPG Academy",
    "site_brand": "RPG Academy",
    "welcome_sign": "Добро пожаловать в панель RPG Academy",
    "custom_css": "admin/rpg-admin.css",
    "copyright": "RPG Academy",
    "search_model": ["game.Track", "game.Mission", "users.User"],
    "hide_apps": ["token_blacklist"],
    "site_logo": "admin/rpg-logo.svg",
    "login_logo": "admin/rpg-logo.svg",
    # the whole user card on one page: the teacher checkbox is not hidden behind a tab
    "changeform_format_overrides": {"users.user": "single"},
    "site_icon": "admin/rpg-logo.svg",
    "topmenu_links": [
        {"name": "Курсы", "model": "game.track"},
        {"name": "Ученики", "url": "/admin/users/user/?is_teacher__exact=0&is_staff__exact=0"},
        {"name": "Преподаватели", "url": "/admin/users/user/?is_teacher__exact=1"},
        {"name": "На сайт", "url": FRONTEND_URL, "new_window": True},
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-users",
        "users.User": "fas fa-user",
        "users.Profile": "fas fa-id-badge",
        "game.Track": "fas fa-book-open",
        "game.Location": "fas fa-map-marked-alt",
        "game.Mission": "fas fa-scroll",
        "game.MissionTask": "fas fa-tasks",
        "game.Rank": "fas fa-medal",
        "game.ClassRole": "fas fa-hat-wizard",
        "game.Progress": "fas fa-chart-line",
        "game.TaskProgress": "fas fa-clipboard-check",
        "game.LeaderboardEntry": "fas fa-trophy",
        "game.Enrollment": "fas fa-user-graduate",
        "game.CodeRun": "fas fa-terminal",
        "game.LearningEvent": "fas fa-stream",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "order_with_respect_to": [
        "game",
        "game.track",
        "game.location",
        "game.mission",
        "game.missiontask",
        "users",
    ],
    "related_modal_active": True,
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "dark_mode_theme": "darkly",
    "navbar": "navbar-light",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_fixed": True,
    "sidebar_nav_compact_style": True,
    "accent": "accent-teal",
    "brand_colour": "navbar-light",
    "actions_sticky_top": True,
}
