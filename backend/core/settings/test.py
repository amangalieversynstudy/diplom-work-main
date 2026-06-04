"""Django settings for tests.

Uses an in-memory SQLite database so tests can run quickly without
requiring the Postgres service to be available during local runs.

If the environment variable ``SQLITE_PATH`` задан, то база будет храниться
в указанном файле, что удобно для ручного запуска приложения без Postgres.
"""

import os

from .base import *  # noqa: F401,F403

# Keep secret key for tests only. Do NOT use in production.
SECRET_KEY = "test-secret-key"

# Use an in-memory SQLite database for tests to avoid external DB deps.
SQLITE_PATH = os.getenv("SQLITE_PATH", ":memory:")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": SQLITE_PATH,
    }
}

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable costly logging during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}

# Tests must not require an external Redis server. base.py points the cache at
# Redis (needed in prod for shared throttle counters), but the suite should run
# anywhere — so use a local in-memory cache. DRF throttling and django-ratelimit
# both rely on the cache; LocMemCache keeps them working without a broker.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Run Celery tasks eagerly in tests (no broker/worker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Simplify i18n in tests to avoid loading system locales that may be missing/corrupted.
LANGUAGE_CODE = "en-us"

# AllowedHostsOriginValidator (ASGI) checks the Origin header against
# ALLOWED_HOSTS. Channels' test communicator does not send one, so we
# permit all origins under the test settings only.
ALLOWED_HOSTS = ["*"]

# The runner's Piston hop makes an outbound HTTP call. Tests must stay offline
# and deterministic, so disable it here — the suite exercises the Docker path
# (mocked) and the local fallback gate without touching the network.
RUNNER_PISTON_URL = ""
