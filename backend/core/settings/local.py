"""Local Django settings used for development."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Development machines usually have no Docker daemon, so allow the local
# subprocess runner there (never in production - see production.py).
RUNNER_ALLOW_UNSAFE_FALLBACK = os.getenv(
    "RUNNER_ALLOW_UNSAFE_FALLBACK", "True"
).lower() in {"1", "true", "yes", "on"}
