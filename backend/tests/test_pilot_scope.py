"""The pilot's numbers come only from pilot content: a self-service teacher's class cannot reach them."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from game.models import Enrollment, Location, Mission, MissionTask, TaskProgress, Track
from game.pilot import build_report

User = get_user_model()


def _course(owner, slug, *, public):
    track = Track.objects.create(slug=slug, title=slug, owner=owner, is_public=public)
    location = Location.objects.create(track=track, title="L")
    mission = Mission.objects.create(location=location, title="M", xp_reward=10)
    task = MissionTask.objects.create(mission=mission, order=1, task_type="quiz", title="Q")
    return track, task


def _consenting(name):
    user = User.objects.create_user(username=name, password="PilotPass123!")
    user.profile.research_consent = True
    user.profile.save(update_fields=["research_consent"])
    return user


@pytest.mark.django_db
def test_a_self_service_class_does_not_change_the_pilot_report():
    staff = User.objects.create_user(username="pilot_staff", password="x", is_staff=True)
    _, public_task = _course(staff, "pilot-public", public=True)
    learner = _consenting("real")
    TaskProgress.objects.create(user=learner, task=public_task, attempts=2, status="completed",
                                last_submitted_at=timezone.now())
    before = build_report()

    farmer = User.objects.create_user(username="farmer", password="x", is_teacher=True)
    klass, class_task = _course(farmer, "farm-class", public=False)
    for i in range(5):
        puppet = _consenting(f"puppet_{i}")
        Enrollment.objects.create(user=puppet, track=klass, consented_at=timezone.now())
        TaskProgress.objects.create(user=puppet, task=class_task, attempts=8, status="in_progress",
                                    last_submitted_at=timezone.now())
    after = build_report()

    assert after["kpi"] == before["kpi"]
    assert after["failure_curve"] == before["failure_curve"]
    assert after["steps"] == before["steps"]
