"""Test bootstrap for pytest.

Adds `backend` to sys.path so the Django project package `core` can be imported
when running pytest from the repository root. Also ensures a sane default
`DJANGO_SETTINGS_MODULE` is set for test runs.
"""

import os
import sys

ROOT = os.path.dirname(__file__)
BACKEND_PATH = os.path.join(ROOT, "backend")

if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

# Ensure pytest-django finds test settings when running from repo root
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.test")
