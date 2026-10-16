"""Classes: a teacher's closed course, joined by a code with the learner's consent.

What must hold: a closed course is invisible without joining; a teacher sees only learners who joined their
classes (or took their public courses); leaving removes the learner from the cabinet; codes cannot be guessed
quickly; teachers cannot join classes.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from game.classes import CODE_ALPHABET, CODE_LENGTH, new_join_code, normalize_code
from game.models import Enrollment, Location, Mission, MissionTask, Progress, TaskProgress, Track

User = get_user_model()

LOOKUP = "/api/classes/lookup/"
JOIN = "/api/classes/join/"


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _user(name, **extra):
    return User.objects.create_user(username=name, password="ClassPass123!", **extra)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _class(owner, slug="class-a", *, active=True):
    """A closed course with a code, as the Studio creates it."""
    track = Track.objects.create(
        slug=slug, title=slug, owner=owner, is_active=active, is_public=False, join_code=new_join_code()
    )
    location = Location.objects.create(track=track, title="Loc")
    mission = Mission.objects.create(location=location, title="M", xp_reward=10)
    task = MissionTask.objects.create(mission=mission, order=1, task_type="quiz")
    return track, mission, task


def _work(learner, mission, task):
    now = timezone.now()
    Progress.objects.create(
        user=learner, mission=mission, status="in_progress", started_at=now, last_started_at=now
    )
    TaskProgress.objects.create(user=learner, task=task, attempts=1, status="in_progress", last_submitted_at=now)


def _roster(teacher):
    return [row["username"] for row in _client(teacher).get("/api/teacher/students/").json()["students"]]


@pytest.mark.django_db
def test_code_alphabet_has_no_lookalikes():
    for ch in "01OIL":
        assert ch not in CODE_ALPHABET
    assert len(new_join_code()) == CODE_LENGTH


def test_codes_are_typed_loosely():
    assert normalize_code(" ab-c d2 ") == "ABCD2"
    assert normalize_code(None) == ""


@pytest.mark.django_db
def test_studio_creates_closed_classes_with_a_code():
    teacher = _user("studio_t", is_teacher=True)
    resp = _client(teacher).post("/api/teacher/studio/tracks/", {"title_ru": "Группа А"}, format="json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_public"] is False
    assert len(body["join_code"]) == CODE_LENGTH
    assert body["join_open"] is True


@pytest.mark.django_db
def test_a_teacher_cannot_set_the_code_or_visibility_by_hand():
    teacher = _user("studio_u", is_teacher=True)
    body = (
        _client(teacher)
        .post(
            "/api/teacher/studio/tracks/",
            {"title_ru": "Группа Б", "is_public": True, "join_code": "AAAAAAAA"},
            format="json",
        )
        .json()
    )
    assert body["is_public"] is False and body["join_code"] != "AAAAAAAA"


@pytest.mark.django_db
def test_new_code_replaces_the_old_one_and_only_for_the_owner():
    teacher, other = _user("t1", is_teacher=True), _user("t2", is_teacher=True)
    track, _, _ = _class(teacher)
    old = track.join_code
    assert _client(other).post(f"/api/teacher/studio/tracks/{track.pk}/new-code/").status_code in (403, 404)
    resp = _client(teacher).post(f"/api/teacher/studio/tracks/{track.pk}/new-code/")
    assert resp.status_code == 200 and resp.json()["join_code"] != old
    track.refresh_from_db()
    assert track.join_code == resp.json()["join_code"]


@pytest.mark.django_db
def test_a_closed_class_is_invisible_until_joined():
    teacher, learner = _user("t3", is_teacher=True), _user("l3")
    track, mission, task = _class(teacher)

    assert track.pk not in [t["id"] for t in _client(learner).get("/api/tracks/").json()]
    assert _client(learner).get(f"/api/missions/{mission.pk}/").status_code == 404
    assert _client(learner).get(f"/api/tasks/{task.pk}/").status_code == 404

    resp = _client(learner).post(JOIN, {"code": track.join_code, "consent": True}, format="json")
    assert resp.status_code == 201

    assert track.pk in [t["id"] for t in _client(learner).get("/api/tracks/").json()]
    assert _client(learner).get(f"/api/missions/{mission.pk}/").status_code == 200


@pytest.mark.django_db
def test_the_owner_sees_their_own_class_but_strangers_do_not():
    teacher, other_teacher = _user("t4", is_teacher=True), _user("t5", is_teacher=True)
    track, _, _ = _class(teacher)
    assert track.pk in [t["id"] for t in _client(teacher).get("/api/tracks/").json()]
    assert track.pk not in [t["id"] for t in _client(other_teacher).get("/api/tracks/").json()]


@pytest.mark.django_db
def test_built_in_public_courses_stay_visible_to_everyone():
    track = Track.objects.create(slug="built-in", title="Built in")  # is_public defaults to True
    learner = _user("l6")
    assert track.pk in [t["id"] for t in _client(learner).get("/api/tracks/").json()]
    assert track.pk in [t["id"] for t in APIClient().get("/api/tracks/").json()]


@pytest.mark.django_db
def test_joining_needs_explicit_consent():
    teacher, learner = _user("t7", is_teacher=True), _user("l7")
    track, _, _ = _class(teacher)
    for body in ({"code": track.join_code}, {"code": track.join_code, "consent": False}, {"code": track.join_code, "consent": "true"}):
        assert _client(learner).post(JOIN, body, format="json").status_code == 400
    assert not Enrollment.objects.filter(user=learner).exists()


@pytest.mark.django_db
def test_a_wrong_code_and_a_missing_class_look_the_same():
    learner = _user("l8")
    assert _client(learner).post(JOIN, {"code": "ZZZZZZZZ", "consent": True}, format="json").status_code == 404
    assert _client(learner).get(LOOKUP, {"code": "ZZZZZZZZ"}).status_code == 404
    assert _client(learner).get(LOOKUP, {"code": ""}).status_code == 400


@pytest.mark.django_db
def test_lookup_shows_who_invites_before_joining():
    teacher, learner = _user("t9", is_teacher=True, display_name="Айгерим"), _user("l9")
    track, _, _ = _class(teacher)
    body = _client(learner).get(LOOKUP, {"code": track.join_code.lower()}).json()
    assert body["teacher"] == "Айгерим" and body["joined"] is False and body["open"] is True
    assert not Enrollment.objects.exists()  # looking is not joining


@pytest.mark.django_db
def test_a_closed_class_takes_no_new_learners_but_keeps_the_old_ones():
    teacher, early, late = _user("t10", is_teacher=True), _user("l10a"), _user("l10b")
    track, _, _ = _class(teacher)
    assert _client(early).post(JOIN, {"code": track.join_code, "consent": True}, format="json").status_code == 201
    track.join_open = False
    track.save(update_fields=["join_open"])
    assert _client(late).post(JOIN, {"code": track.join_code, "consent": True}, format="json").status_code == 403
    # the one who is already in is unaffected, and joining twice is harmless
    assert _client(early).post(JOIN, {"code": track.join_code, "consent": True}, format="json").status_code == 200
    assert Enrollment.objects.filter(track=track).count() == 1


@pytest.mark.django_db
def test_teachers_cannot_join_classes():
    teacher, other = _user("t11", is_teacher=True), _user("t12", is_teacher=True)
    track, _, _ = _class(teacher)
    assert _client(teacher).post(JOIN, {"code": track.join_code, "consent": True}, format="json").status_code == 400
    assert _client(other).post(JOIN, {"code": track.join_code, "consent": True}, format="json").status_code == 400
    assert not Enrollment.objects.exists()


@pytest.mark.django_db
def test_a_draft_class_cannot_be_joined():
    teacher, learner = _user("t13", is_teacher=True), _user("l13")
    track, _, _ = _class(teacher, active=False)
    assert _client(learner).post(JOIN, {"code": track.join_code, "consent": True}, format="json").status_code == 404


@pytest.mark.django_db
def test_joining_requires_signing_in():
    assert APIClient().post(JOIN, {"code": "AAAAAAAA", "consent": True}, format="json").status_code in (401, 403)
    assert APIClient().get(LOOKUP, {"code": "AAAAAAAA"}).status_code in (401, 403)


@pytest.mark.django_db
def test_guessing_codes_is_throttled(monkeypatch):
    from game.throttles import ClassJoinThrottle

    monkeypatch.setitem(ClassJoinThrottle.THROTTLE_RATES, "class_join", "3/hour")
    learner = _user("l14")
    client = _client(learner)
    codes = [client.get(LOOKUP, {"code": "ZZZZZZZZ"}).status_code for _ in range(5)]
    assert codes[:3] == [404, 404, 404]
    assert 429 in codes[3:]


@pytest.mark.django_db
def test_a_teacher_sees_only_learners_who_joined_their_class():
    teacher = _user("t15", is_teacher=True)
    track, mission, task = _class(teacher)
    member, stranger = _user("member"), _user("stranger")
    _client(member).post(JOIN, {"code": track.join_code, "consent": True}, format="json")
    # a stranger who somehow has progress in the closed course (e.g. an old row) is still not visible
    _work(stranger, mission, task)

    assert _roster(teacher) == ["member"]


@pytest.mark.django_db
def test_leaving_removes_the_learner_from_the_cabinet_everywhere():
    teacher = _user("t16", is_teacher=True)
    track, mission, task = _class(teacher)
    learner = _user("leaver")
    _client(learner).post(JOIN, {"code": track.join_code, "consent": True}, format="json")
    _work(learner, mission, task)
    assert _roster(teacher) == ["leaver"]
    assert _client(teacher).get(f"/api/teacher/students/{learner.pk}/learning/").status_code == 200

    assert _client(learner).delete(f"/api/classes/{track.pk}/leave/").status_code == 204

    assert _roster(teacher) == []
    assert _client(teacher).get(f"/api/teacher/students/{learner.pk}/learning/").status_code == 404
    metrics = _client(teacher).get("/api/analytics/metrics/").json()
    assert metrics["meta"]["learners"] == 0
    assert _client(teacher).get("/api/analytics/early-warning/").json()["students"] == []
    # the learner's own record is untouched
    assert Progress.objects.filter(user=learner).exists()


@pytest.mark.django_db
def test_my_classes_lists_only_mine():
    teacher = _user("t17", is_teacher=True)
    track, _, _ = _class(teacher)
    mine, other = _user("l17"), _user("l17b")
    _client(mine).post(JOIN, {"code": track.join_code, "consent": True}, format="json")
    assert [row["track_id"] for row in _client(mine).get("/api/classes/mine/").json()] == [track.pk]
    assert _client(other).get("/api/classes/mine/").json() == []
    assert _client(other).delete(f"/api/classes/{track.pk}/leave/").status_code == 404


@pytest.mark.django_db
def test_a_second_teacher_never_sees_another_teachers_class_members():
    teacher_a, teacher_b = _user("ta", is_teacher=True), _user("tb", is_teacher=True)
    track_a, mission_a, task_a = _class(teacher_a, "class-ta")
    _class(teacher_b, "class-tb")
    learner = _user("shared")
    _client(learner).post(JOIN, {"code": track_a.join_code, "consent": True}, format="json")
    _work(learner, mission_a, task_a)

    assert _roster(teacher_a) == ["shared"]
    assert _roster(teacher_b) == []
    assert _client(teacher_b).get(f"/api/teacher/students/{learner.pk}/learning/").status_code == 404


@pytest.mark.django_db
def test_public_courses_keep_the_old_rule_progress_is_enough():
    teacher = _user("t18", is_teacher=True)
    track = Track.objects.create(slug="public-owned", title="Public", owner=teacher)  # public by default
    location = Location.objects.create(track=track, title="Loc")
    mission = Mission.objects.create(location=location, title="M", xp_reward=10)
    task = MissionTask.objects.create(mission=mission, order=1, task_type="quiz")
    learner = _user("l18")
    _work(learner, mission, task)

    assert _roster(teacher) == ["l18"]
