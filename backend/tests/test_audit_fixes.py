"""Fixes from the local end-to-end audit of 2026-11-09 (learner, teacher and data-collection paths)."""

import csv
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import LearningEvent, Location, Mission, MissionTask, TaskProgress, Track

User = get_user_model()

pytestmark = pytest.mark.django_db

HINTS = [{"ru": "Подумай о цикле.", "en": "Think of a loop."}]


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_items_help_only_with_the_open_unsolved_step():
    learner = User.objects.create_user("learner", "l@example.com", "S3cure-pass-1")
    learner.profile.hint_scrolls = 3
    learner.profile.save()
    track = Track.objects.create(slug="py", title="Python", is_active=True, is_public=True)
    mission = Mission.objects.create(location=Location.objects.create(track=track, title="L"), title="M")
    first = MissionTask.objects.create(mission=mission, order=1, task_type="code", data={"hints": HINTS})
    second = MissionTask.objects.create(mission=mission, order=2, task_type="code", data={"hints": HINTS})
    api = _client(learner)

    def use(task):
        return api.post("/api/profile/use-item/", {"item_type": "hint_scrolls", "task_id": task.pk}, format="json")

    locked = use(second)  # the first step is not solved yet
    assert locked.status_code == 409 and locked.json()["code"] == "step_locked"
    assert use(first).status_code == 200
    TaskProgress.objects.create(user=learner, task=first, status="completed", attempts=1)
    solved = use(first)
    assert solved.status_code == 409 and solved.json()["code"] == "step_solved"
    learner.profile.refresh_from_db()
    assert learner.profile.hint_scrolls == 2  # only the one real use was spent


def test_a_studio_code_step_needs_an_expected_output_or_a_hidden_check():
    teacher = User.objects.create_user("teach", "t@example.com", "S3cure-pass-1", is_teacher=True)
    track = Track.objects.create(slug="own", title="Own", owner=teacher, is_public=False)
    mission = Mission.objects.create(location=Location.objects.create(track=track, title="L"), title="M")
    api = _client(teacher)
    payload = {"mission": mission.pk, "task_type": "code", "title_ru": "Шаг", "order": 1}
    bare = api.post("/api/teacher/studio/tasks/", {**payload, "data": {"starter": "x = 1"}}, format="json")
    assert bare.status_code == 400
    assert "засчитается за любой код" in bare.content.decode()
    checked = api.post(
        "/api/teacher/studio/tasks/", {**payload, "data": {"starter": "", "hidden_check": "assert x == 1"}}, format="json"
    )
    assert checked.status_code == 201, checked.content


def test_personal_variants_alone_do_not_make_a_code_step_checkable():
    teacher = User.objects.create_user("teachv", "tv@example.com", "S3cure-pass-1", is_teacher=True)
    track = Track.objects.create(slug="ownv", title="Own", owner=teacher, is_public=False)
    mission = Mission.objects.create(location=Location.objects.create(track=track, title="L"), title="M")
    api = _client(teacher)
    payload = {"mission": mission.pk, "task_type": "code", "title_ru": "Шаг", "order": 1}
    variants = [{"vars": {"n": 1}}, {"vars": {"n": 2}}]
    bare = api.post("/api/teacher/studio/tasks/", {**payload, "data": {"starter": "", "variants": variants}}, format="json")
    assert bare.status_code == 400  # no expected output anywhere: any code would pass
    each = [{"vars": {"n": 1}, "expected_output": "1"}, {"vars": {"n": 2}, "expected_output": "2"}]
    ok = api.post("/api/teacher/studio/tasks/", {**payload, "data": {"starter": "", "variants": each}}, format="json")
    assert ok.status_code == 201, ok.content


def test_the_learning_export_takes_the_research_cohort_and_the_period(tmp_path):
    start = timezone.now() - timedelta(days=10)
    end = timezone.now() - timedelta(days=1)

    def learner(name, joined, consent=True):
        user = User.objects.create_user(name, f"{name}@example.com", "S3cure-pass-1")
        User.objects.filter(pk=user.pk).update(date_joined=joined)
        user.profile.research_consent = consent
        user.profile.save()
        return user

    rehearsal = learner("rehearsal", start - timedelta(days=5))  # signed up before the pilot
    member = learner("member", start + timedelta(days=1))
    learner("declined", start + timedelta(days=1), consent=False)
    for user, when in ((rehearsal, start + timedelta(days=2)), (member, start + timedelta(days=2)), (member, end + timedelta(hours=1))):
        event = LearningEvent.objects.create(user=user, event_type=LearningEvent.TASK_OPENED)
        LearningEvent.objects.filter(pk=event.pk).update(created_at=when)

    with override_settings(PILOT_STARTED_AT=start.isoformat(), PILOT_ENDED_AT=end.isoformat()):
        call_command("export_learning_data", out=str(tmp_path))

    def rows(name):
        with open(tmp_path / name, encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    assert len(rows("users.csv")) == 1  # only the member: no rehearsal account, nobody without consent
    assert len(rows("events.csv")) == 1  # the event after PILOT_ENDED_AT is cut off
