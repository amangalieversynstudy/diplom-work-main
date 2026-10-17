"""Shared scope and trust helpers of game/classes.py."""

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from game.classes import (
    TASK_TRACK,
    is_vetted_teacher,
    owner_scope,
    paying_tracks_q,
    pays_globally,
    visible_events,
    visible_learners,
    visible_work,
    with_fresh_code,
)
from game.models import (
    Enrollment,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    TaskProgress,
    Track,
)

User = get_user_model()
PILOT = SimpleNamespace(is_superuser=True)


def _user(name, **extra):
    return User.objects.create_user(username=name, password="HelperPass123!", **extra)


def _course(owner, slug, *, public):
    track = Track.objects.create(slug=slug, title=slug, owner=owner, is_public=public)
    location = Location.objects.create(track=track, title="L")
    mission = Mission.objects.create(location=location, title="M", xp_reward=10)
    task = MissionTask.objects.create(mission=mission, order=1, task_type="quiz")
    return track, mission, task


def test_the_pilot_namespace_sees_everything_without_touching_pk():
    assert visible_work(PILOT, TASK_TRACK) == Q()
    assert visible_events(PILOT) == Q()
    assert owner_scope(PILOT) is None
    assert is_vetted_teacher(PILOT) is True


@pytest.mark.django_db
def test_who_is_vetted():
    assert is_vetted_teacher(_user("staff_v", is_staff=True)) is True
    assert is_vetted_teacher(_user("su_v", is_staff=True, is_superuser=True)) is True
    assert is_vetted_teacher(_user("self_v", is_teacher=True)) is False
    # a self-service teacher who was also made staff stays self-service
    assert is_vetted_teacher(_user("both_v", is_teacher=True, is_staff=True)) is False
    assert is_vetted_teacher(_user("learner_v")) is False
    assert is_vetted_teacher(None) is False


@pytest.mark.django_db
def test_rows_of_a_closed_course_count_only_while_enrolled():
    teacher = _user("t_rows", is_staff=True)
    _, _, public_task = _course(teacher, "pub-rows", public=True)
    klass, _, class_task = _course(teacher, "cls-rows", public=False)
    learner = _user("l_rows")
    for task in (public_task, class_task):
        TaskProgress.objects.create(user=learner, task=task, attempts=1, status="in_progress")
    enrollment = Enrollment.objects.create(user=learner, track=klass, consented_at=timezone.now())

    def seen():
        rows = TaskProgress.objects.filter(visible_work(teacher, TASK_TRACK))
        return sorted(rows.values_list("task_id", flat=True))

    assert seen() == sorted([public_task.pk, class_task.pk])
    enrollment.delete()
    assert seen() == [public_task.pk]
    other = _user("t_other", is_staff=True)
    assert not TaskProgress.objects.filter(visible_work(other, TASK_TRACK)).exists()


@pytest.mark.django_db
def test_visible_events_keeps_mission_only_events():
    teacher = _user("t_ev", is_staff=True)
    _, mission, task = _course(teacher, "pub-ev", public=True)
    learner = _user("l_ev")
    LearningEvent.objects.create(user=learner, event_type=LearningEvent.MISSION_STARTED, mission=mission)
    LearningEvent.objects.create(user=learner, event_type=LearningEvent.TASK_OPENED, task=task)
    assert LearningEvent.objects.filter(visible_events(teacher)).count() == 2


@pytest.mark.django_db
def test_only_vetted_owners_see_every_learner_of_a_public_course():
    vetted = _user("t_vet", is_staff=True)
    self_service = _user("t_self", is_teacher=True)
    learner = _user("l_pub")
    for owner, slug in ((vetted, "pub-vet"), (self_service, "pub-self")):
        _, mission, _ = _course(owner, slug, public=True)
        Progress.objects.create(user=learner, mission=mission, status="in_progress", started_at=timezone.now())

    assert list(visible_learners(vetted)) == [learner]
    assert list(visible_learners(self_service)) == []


@pytest.mark.django_db
def test_who_gets_global_rewards():
    vetted = _user("t_pay", is_staff=True)
    self_service = _user("t_pay2", is_teacher=True)
    learner = _user("l_pay")
    public, _, _ = _course(vetted, "pay-pub", public=True)
    vetted_class, _, _ = _course(vetted, "pay-vc", public=False)
    self_class, _, _ = _course(self_service, "pay-sc", public=False)
    orphan, _, _ = _course(None, "pay-orphan", public=False)
    _course(learner, "pay-own", public=True)

    assert pays_globally(learner, None) is True
    assert pays_globally(learner, public) is True
    assert pays_globally(learner, vetted_class) is True
    assert pays_globally(learner, self_class) is False
    assert pays_globally(learner, orphan) is False
    # teachers never earn, and an owner never earns in their own course
    assert pays_globally(vetted, public) is False
    assert pays_globally(self_service, public) is False

    paying = set(
        Mission.objects.filter(paying_tracks_q(learner, "location__track")).values_list(
            "location__track__slug", flat=True
        )
    )
    assert paying == {"pay-pub", "pay-vc"}


@pytest.mark.django_db
def test_with_fresh_code_retries_when_the_code_is_taken(monkeypatch):
    import game.classes as classes

    Track.objects.create(slug="taken", title="Taken", join_code="TAKEN234")
    codes = iter(["TAKEN234", "FRESH234"])
    monkeypatch.setattr(classes, "new_join_code", lambda: next(codes))
    track = Track.objects.create(slug="new-one", title="New")

    def write(code):
        track.join_code = code
        track.save(update_fields=["join_code"])
        return code

    assert with_fresh_code(write) == "FRESH234"
    track.refresh_from_db()
    assert track.join_code == "FRESH234"
