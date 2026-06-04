"""Local Django settings used for development."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Convenience default for local dev so teacher registration works out of the
# box. Uses the env value when set; never affects production (which reads
# TEACHER_INVITE_CODE straight from env via base settings).
TEACHER_INVITE_CODE = TEACHER_INVITE_CODE or "TEACH-DEV"
