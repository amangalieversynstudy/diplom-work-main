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
