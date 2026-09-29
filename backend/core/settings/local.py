"""Local Django settings used for development."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Convenience default for local dev so teacher registration works out of the
# box. Uses the env value when set; never affects production (which reads
# TEACHER_INVITE_CODE straight from env via base settings).
TEACHER_INVITE_CODE = TEACHER_INVITE_CODE or "TEACH-DEV"

# Development machines usually have no Docker daemon, so allow the local
# subprocess runner there (never in production - see production.py).
RUNNER_ALLOW_UNSAFE_FALLBACK = os.getenv(
    "RUNNER_ALLOW_UNSAFE_FALLBACK", "True"
).lower() in {"1", "true", "yes", "on"}
