"""Pilot teachers: the invite code in the profile, the demo course in one click, the «Глазами студента» switch."""

import contextlib
import io

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from game.demo_course import DEMO_TITLE_RU
from game.models import Location, Mission, MissionTask, Track
from game.services import code_run_passed, hidden_check_of
from game.variants import personalize, variants_of

User = get_user_model()
pytestmark = pytest.mark.django_db

ACTIVATE = "/api/auth/activate-teacher/"
DEMO = "/api/teacher/studio/tracks/demo/"
CODE = "PILOT-TEST"


@pytest.fixture(autouse=True)
def _fresh_throttles():
    cache.clear()
    yield
    cache.clear()


def _client(user=None, **headers):
    """A client signed in with a real JWT: force_authenticate would skip the authentication class that reads
    the «Глазами студента» header."""
    client = APIClient(**headers)
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def learner():
    return User.objects.create_user("learner", "l@example.com", "S3cure-pass-1")


@pytest.fixture
def teacher():
    return User.objects.create_user("pilot", "p@example.com", "S3cure-pass-1", is_teacher=True)


# ── «Активировать доступ преподавателя» ─────────────────────────────────────


@override_settings(TEACHER_INVITE_CODE=CODE)
def test_learner_activates_the_teacher_role_with_the_code(learner):
    resp = _client(learner).post(ACTIVATE, {"code": "pilot test"}, format="json")
    assert resp.status_code == 200
    assert resp.json() == {"is_teacher": True, "is_staff": False, "can_teach": True}
    learner.refresh_from_db()
    assert (learner.is_teacher, learner.is_staff) == (True, False)


@override_settings(TEACHER_INVITE_CODE=CODE)
@pytest.mark.parametrize("code", ["WRONG", "", "КОД"])
def test_a_wrong_empty_or_non_ascii_code_changes_nothing(learner, code):
    resp = _client(learner).post(ACTIVATE, {"code": code}, format="json")
    assert resp.status_code == 400
    assert "code" in resp.json()
    learner.refresh_from_db()
    assert learner.can_teach is False


@override_settings(TEACHER_INVITE_CODE="")
def test_a_switched_off_code_accepts_nothing(learner):
    assert _client(learner).post(ACTIVATE, {"code": ""}, format="json").status_code == 400
    assert _client(learner).post(ACTIVATE, {"code": "PILOT-2026"}, format="json").status_code == 400


def test_a_teacher_needs_no_code_and_stays_as_is():
    vetted = User.objects.create_user("vetted", "v@example.com", "S3cure-pass-1", is_staff=True)
    resp = _client(vetted).post(ACTIVATE, {}, format="json")
    assert resp.status_code == 200 and resp.json()["can_teach"] is True
    vetted.refresh_from_db()
    assert (vetted.is_staff, vetted.is_teacher) == (True, False)  # a vetted teacher is not demoted


def test_activation_needs_a_signed_in_user():
    assert _client().post(ACTIVATE, {"code": CODE}, format="json").status_code == 401


@override_settings(TEACHER_INVITE_CODE=CODE)
def test_the_code_cannot_be_guessed_by_brute_force(learner):
    rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["teacher_code"]
    limit = int(rate.split("/")[0])
    client = _client(learner)
    for _ in range(limit):
        assert client.post(ACTIVATE, {"code": "GUESS"}, format="json").status_code == 400
    assert client.post(ACTIVATE, {"code": CODE}, format="json").status_code == 429


# ── «Развернуть демо-пример» ────────────────────────────────────────────────


def test_demo_course_is_a_published_closed_class_with_three_step_types(teacher):
    resp = _client(teacher).post(DEMO)
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["created"] is True and body["title_ru"] == DEMO_TITLE_RU
    assert body["locations_count"] == 1 and body["missions_count"] == 1
    track = Track.objects.get(pk=body["id"])
    assert track.owner == teacher and track.is_active and not track.is_public and track.join_code
    mission = Mission.objects.get(location__track=track)
    assert mission.is_active
    steps = list(MissionTask.objects.filter(mission=mission).order_by("order"))
    assert [s.task_type for s in steps] == ["story", "quiz", "code"]


def test_a_second_click_opens_the_same_demo(teacher):
    first = _client(teacher).post(DEMO).json()
    again = _client(teacher).post(DEMO)
    assert again.status_code == 200
    assert again.json()["id"] == first["id"] and again.json()["created"] is False
    assert Track.objects.filter(owner=teacher).count() == 1


def test_every_variant_of_the_demo_code_step_is_solvable(teacher):
    """The reference solution passes the expected output and the hidden check of each learner's variant."""
    _client(teacher).post(DEMO)
    step = MissionTask.objects.get(mission__location__track__owner=teacher, task_type="code")
    variants = variants_of(step.data)
    assert len(variants) >= 2
    for variant in variants:
        # a step with only this variant: whoever gets it is graded on it
        single = MissionTask(pk=step.pk, task_type="code", data={**step.data, "variants": [variant]})
        personal = personalize(single, user_id=1)
        source = personal.data["starter"] + 'print("Привет, " + name + "!")\n'
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(source, {})  # noqa: S102 - our own reference solution
            exec(source + "\n" + hidden_check_of(personal), {})  # noqa: S102 - the hidden check must pass too
        assert code_run_passed(personal, 0, out.getvalue().splitlines()[0]), variant


def test_demo_respects_the_course_quota(teacher):
    for i in range(settings.STUDIO_LIMITS["tracks_per_teacher"]):
        Track.objects.create(slug=f"t{i}", title=f"t{i}", owner=teacher)
    resp = _client(teacher).post(DEMO)
    assert resp.status_code == 400
    assert not Track.objects.filter(owner=teacher, title_ru=DEMO_TITLE_RU).exists()


def test_a_learner_cannot_deploy_a_demo(learner):
    assert _client(learner).post(DEMO).status_code == 403


# ── «Глазами студента» ──────────────────────────────────────────────────────


@pytest.fixture
def course_with_draft(teacher):
    track = Track.objects.create(slug="mine", title="Mine", owner=teacher, is_active=True, is_public=False)
    location = Location.objects.create(track=track, title="L", order=1)
    live = Mission.objects.create(location=location, title="Live", order=1, is_active=True)
    draft = Mission.objects.create(location=location, title="Draft", order=2, is_active=False)
    return live, draft


def _mission_ids(client):
    rows = client.get("/api/missions/").json()
    rows = rows.get("results", rows) if isinstance(rows, dict) else rows
    return {row["id"] for row in rows}


def test_teacher_sees_own_draft_but_not_in_student_view(teacher, course_with_draft):
    live, draft = course_with_draft
    assert _mission_ids(_client(teacher)) >= {live.pk, draft.pk}
    as_learner = _mission_ids(_client(teacher, HTTP_X_VIEW_AS="student"))
    assert live.pk in as_learner and draft.pk not in as_learner


def test_the_header_gives_a_learner_nothing(learner, course_with_draft):
    live, draft = course_with_draft
    assert draft.pk not in _mission_ids(_client(learner, HTTP_X_VIEW_AS="teacher"))


def test_the_cors_preflight_allows_the_view_as_header():
    assert "x-view-as" in settings.CORS_ALLOW_HEADERS
