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


import pytest  # noqa: E402


@pytest.fixture
def finish_mission():
    """Solve every required step of a mission the way a learner does.

    Missions can only be completed once their required tasks are solved on the
    server. Test missions get a story step (accepted on submit) when they have
    none; quiz and code steps have their own dedicated tests.
    """

    def _finish(client, mission):
        from game.models import MissionTask

        if not mission.tasks.filter(is_required=True).exists():
            MissionTask.objects.create(
                mission=mission, order=1, task_type="story", title="Intro"
            )
        for task in mission.tasks.filter(is_required=True).order_by("order", "id"):
            response = client.post(
                f"/api/mission-tasks/{task.id}/submit/", {}, format="json"
            )
            assert response.status_code == 200, response.content

    return _finish


@pytest.fixture(autouse=True)
def _clean_cache():
    """Throttle/rate-limit counters live in the cache. The cache outlives a test
    while user ids restart after each DB rollback, so without this a later test
    inherits an earlier test's request count and gets a spurious 429."""
    from django.core.cache import cache

    cache.clear()
    yield
