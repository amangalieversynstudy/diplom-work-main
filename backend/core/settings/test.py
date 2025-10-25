"""Django settings for tests.

Uses an in-memory SQLite database so tests can run quickly without
requiring the Postgres service to be available during local runs.
"""

from .base import *  # noqa: F401,F403

# Keep secret key for tests only. Do NOT use in production.
SECRET_KEY = "test-secret-key"

# Use an in-memory SQLite database for tests to avoid external DB deps.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
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
