"""Digital footprint: code runs, timeline events, consent, export, retention."""

import csv
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from game.footprint import classify_run, exception_name, finish_code_run, find_task
from game.management.commands.export_learning_data import pseudonym
from game.models import (
    CodeRun,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    TaskProgress,
    Track,
)
from game.runner import (
    REASON_OUTPUT_LIMIT,
    REASON_RUNNER_ERROR,
    REASON_STOPPED,
    REASON_TIMEOUT,
    REASON_UNAVAILABLE,
)
from game.throttles import allow_code_run

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user("student", "student@example.com", "S3cure-pass-1")


@pytest.fixture
def client(student):
    api = APIClient()
    api.force_authenticate(student)
    return api


@pytest.fixture
def course():
    track = Track.objects.create(slug="py", title="Python", is_active=True)
    location = Location.objects.create(track=track, title="Island", order=1)
    mission = Mission.objects.create(location=location, title="Basics", order=1, xp_reward=50)
    story = MissionTask.objects.create(mission=mission, order=1, task_type="story", title="S")
    quiz = MissionTask.objects.create(
        mission=mission,
        order=2,
        task_type="quiz",
        data={"correct_answer": "str", "options": [{"value": "str", "label": "str"}]},
    )
    code = MissionTask.objects.create(
        mission=mission,
        order=3,
        task_type="code",
        data={"expected_output": "ok", "starter": "print(1)"},
    )
    return mission, story, quiz, code


def run(student, task, *, stdout="", stderr="", exit_code=0, reasons=(), code="print(1)"):
    return finish_code_run(
        student,
        task,
        code=code,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        duration=0.25,
        reasons=set(reasons),
    )


# ── reading Python errors ───────────────────────────────────────────────────

TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "<string>", line 1, in <module>\n'
    "{last}\n"
)


@pytest.mark.parametrize(
    "stderr, expected",
    [
        (TRACEBACK.format(last="NameError: name 'x' is not defined"), "NameError"),
        (TRACEBACK.format(last="ZeroDivisionError: division by zero"), "ZeroDivisionError"),
        (TRACEBACK.format(last="ModuleNotFoundError: No module named 'q'"), "ModuleNotFoundError"),
        ('  File "<string>", line 1\n    print(\n         ^\nSyntaxError: \'(\' was never closed\n', "SyntaxError"),
        ("IndentationError: unexpected indent\n", "IndentationError"),
        (TRACEBACK.format(last="requests.exceptions.HTTPError: 404"), "HTTPError"),
        ("Exception: boom\n", "Exception"),
        ("SystemExit: 3\n", "SystemExit"),
        ("KeyboardInterrupt\n", "KeyboardInterrupt"),
        ("", ""),
        ("just some warning text\n", ""),
    ],
)
def test_exception_name(stderr, expected):
    assert exception_name(stderr) == expected


@pytest.mark.parametrize(
    "exit_code, stderr, reasons, passed, expected",
    [
        (0, "", (), None, ("success", "", "")),
        (0, "", (), True, ("success", "", "")),
        (0, "", (), False, ("wrong_output", "", "")),
        (1, TRACEBACK.format(last="NameError: name 'x' is not defined"), (), False,
         ("error", "NameError", "NameError: name 'x' is not defined")),
        (3, "", (), False, ("error", "NonZeroExit", "")),
        (137, "", (REASON_TIMEOUT,), False, ("timeout", "Timeout", "")),
        (137, "", (REASON_OUTPUT_LIMIT,), False, ("output_limit", "OutputLimit", "")),
        (-1, "", (REASON_RUNNER_ERROR,), None, ("runner_error", "", "")),
        (-1, "", (REASON_UNAVAILABLE,), None, ("runner_error", "", "")),
        (0, "", (REASON_STOPPED,), None, ("runner_error", "", "")),
    ],
)
def test_classify_run(exit_code, stderr, reasons, passed, expected):
    assert classify_run(exit_code, stderr, reasons, passed) == expected


# ── recording code runs ─────────────────────────────────────────────────────


def test_graded_success_is_recorded_with_its_attempt_number(student, course):
    *_, code = course
    verdict = run(student, code, stdout="ok\n")
    assert verdict["passed"] is True
    assert "counted" not in verdict  # internal, never sent to the browser
    record = CodeRun.objects.get()
    assert (record.user, record.task, record.outcome) == (student, code, "success")
    assert (record.passed, record.attempt_no, record.after_solved) == (True, 1, False)
    assert record.exit_code == 0
    assert record.duration_ms == 250
    assert record.code_length == len("print(1)")
    assert record.stdout_size == 3


def test_failures_are_classified_and_numbered(student, course):
    *_, code = course
    run(student, code, stdout="nope\n")
    run(
        student,
        code,
        stderr=TRACEBACK.format(last="NameError: name 'x' is not defined"),
        exit_code=1,
    )
    run(student, code, stdout="ok\n")
    first, second, third = CodeRun.objects.order_by("id")
    assert (first.outcome, first.attempt_no, first.passed) == ("wrong_output", 1, False)
    assert (second.outcome, second.error_type, second.attempt_no) == ("error", "NameError", 2)
    assert second.error_message == "NameError: name 'x' is not defined"
    assert (third.outcome, third.attempt_no, third.passed) == ("success", 3, True)


def test_runs_after_the_solve_are_flagged_and_do_not_count(student, course):
    *_, code = course
    run(student, code, stdout="ok\n")
    run(student, code, stdout="ok\n")
    _, again = CodeRun.objects.order_by("id")
    assert again.after_solved is True
    assert again.attempt_no == 1  # frozen at the first success
    assert TaskProgress.objects.get(user=student, task=code).attempts == 1


@pytest.mark.parametrize("reason", [REASON_RUNNER_ERROR, REASON_UNAVAILABLE, REASON_STOPPED])
def test_infrastructure_failures_are_not_a_failed_attempt(student, course, reason):
    """A broken sandbox must not look like the learner failing the task."""
    *_, code = course
    verdict = run(student, code, exit_code=-1, reasons={reason})
    assert verdict is None
    assert not TaskProgress.objects.filter(user=student, task=code).exists()
    record = CodeRun.objects.get()
    assert record.outcome == "runner_error"
    assert (record.passed, record.attempt_no) == (None, None)


def test_timeouts_count_as_attempts(student, course):
    *_, code = course
    run(student, code, exit_code=137, reasons={REASON_TIMEOUT})
    assert CodeRun.objects.get().outcome == "timeout"
    assert TaskProgress.objects.get(user=student, task=code).attempts == 1


def test_free_practice_runs_are_recorded_without_a_task(student):
    assert run(student, None, stdout="hi\n") is None
    record = CodeRun.objects.get()
    assert (record.task, record.outcome, record.passed) == (None, "success", None)
    assert not TaskProgress.objects.exists()


def test_recording_never_breaks_grading(student, course):
    *_, code = course
    with patch.object(CodeRun.objects, "create", side_effect=RuntimeError("db down")):
        verdict = run(student, code, stdout="ok\n")
    assert verdict["passed"] is True
    assert TaskProgress.objects.get(user=student, task=code).status == "completed"


# ── timeline events ─────────────────────────────────────────────────────────


def events(kind):
    return list(LearningEvent.objects.filter(event_type=kind).order_by("id"))


def test_login_is_logged_only_when_it_succeeds(student):
    api = APIClient()
    api.post("/api/auth/login/", {"username": "student", "password": "wrong"}, format="json")
    assert events("login") == []
    ok = api.post(
        "/api/auth/login/", {"username": "student", "password": "S3cure-pass-1"}, format="json"
    )
    assert ok.status_code == 200
    (event,) = events("login")
    assert event.user == student


def test_a_failing_event_write_never_breaks_login(student):
    with patch.object(LearningEvent.objects, "create", side_effect=RuntimeError("db down")):
        response = APIClient().post(
            "/api/auth/login/", {"username": "student", "password": "S3cure-pass-1"}, format="json"
        )
    assert response.status_code == 200
    assert "access" in response.json()


def test_mission_lifecycle_is_logged(client, student, course):
    mission, story, quiz, code = course
    client.post(f"/api/missions/{mission.id}/start/")
    client.post(f"/api/mission-tasks/{story.id}/submit/", {}, format="json")
    client.post(f"/api/mission-tasks/{quiz.id}/submit/", {"answer": "nope"}, format="json")
    client.post(f"/api/mission-tasks/{quiz.id}/submit/", {"answer": "str"}, format="json")
    run(student, code, stdout="ok\n")
    client.post(f"/api/missions/{mission.id}/complete/")

    (started,) = events("mission_started")
    assert (started.mission, started.meta["attempt"]) == (mission, 1)

    submitted = events("task_submitted")
    assert [e.meta["correct"] for e in submitted] == [True, False, True]
    assert [e.meta["attempt"] for e in submitted] == [1, 1, 2]
    assert all(e.meta["after_solved"] is False for e in submitted)
    assert submitted[1].task == quiz and submitted[1].meta["task_type"] == "quiz"

    (done,) = events("mission_completed")
    assert done.meta == {"xp_added": 50, "stars": 2, "first_time": True}


def test_resubmitting_a_solved_step_is_flagged(client, course):
    _, story, *_ = course
    client.post(f"/api/mission-tasks/{story.id}/submit/", {}, format="json")
    client.post(f"/api/mission-tasks/{story.id}/submit/", {}, format="json")
    first, second = events("task_submitted")
    assert first.meta["after_solved"] is False
    assert second.meta["after_solved"] is True


def test_hints_are_logged_against_the_task(client, student, course):
    *_, code = course
    client.post("/api/profile/use-item/", {"item_type": "hint_scrolls", "task_id": code.id}, format="json")
    client.post("/api/profile/use-item/", {"item_type": "skeleton_scrolls", "task_id": code.id}, format="json")
    (hint,) = events("hint_used")
    (skeleton,) = events("skeleton_used")
    assert (hint.task, hint.mission) == (code, code.mission)
    assert skeleton.task == code


def test_hint_without_or_with_a_bogus_task_is_still_logged_and_never_fails(client, student):
    for body in ({}, {"task_id": 999999}, {"task_id": "x"}, {"task_id": True}):
        response = client.post(
            "/api/profile/use-item/", {"item_type": "hint_scrolls", **body}, format="json"
        )
        assert response.status_code == 200
    assert [e.task for e in events("hint_used")] == [None] * 4


def test_an_empty_inventory_logs_nothing(client, student):
    student.profile.hint_scrolls = 0
    student.profile.save()
    response = client.post("/api/profile/use-item/", {"item_type": "hint_scrolls"}, format="json")
    assert response.status_code == 400
    assert events("hint_used") == []


def test_ai_help_is_logged_against_the_task(client, course):
    *_, code = course
    with patch("game.views.AIAssistView._call_gemini", return_value=("a hint", True)):
        client.post(
            "/api/ai-assist/",
            {"task_description": "do it", "code": "x", "task_id": code.id},
            format="json",
        )
    with patch("game.views._call_gemini_chat", return_value=("a reply", True)):
        client.post(
            "/api/ai-mentor/",
            {"messages": [{"role": "user", "content": "help"}], "task_id": code.id},
            format="json",
        )
    (assist,) = events("ai_hint_used")
    (mentor,) = events("ai_mentor_used")
    assert assist.task == mentor.task == code


def test_failed_ai_calls_are_not_logged(client, course):
    with patch("game.views.AIAssistView._call_gemini", return_value=("sorry", False)):
        client.post("/api/ai-assist/", {"task_description": "do it"}, format="json")
    assert events("ai_hint_used") == []


def test_task_opened_endpoint(client, student, course):
    _, story, *_ = course
    ok = client.post(
        "/api/events/", {"event_type": "task_opened", "task_id": story.id}, format="json"
    )
    assert ok.status_code == 204
    (event,) = events("task_opened")
    assert (event.user, event.task, event.mission) == (student, story, story.mission)


@pytest.mark.parametrize(
    "body, status",
    [
        ({"event_type": "mission_completed", "task_id": 1}, 400),  # not client-reportable
        ({"event_type": "login"}, 400),
        ({"event_type": "hint_used", "task_id": 1}, 400),
        ({"event_type": "task_opened"}, 404),
        ({"event_type": "task_opened", "task_id": 999999}, 404),
        ({"event_type": "task_opened", "task_id": "1"}, 404),
    ],
)
def test_task_opened_endpoint_rejects_bad_input(client, course, body, status):
    assert client.post("/api/events/", body, format="json").status_code == status
    assert LearningEvent.objects.count() == 0


def test_events_endpoint_requires_login_and_hides_drafts(course):
    _, story, *_ = course
    body = {"event_type": "task_opened", "task_id": story.id}
    assert APIClient().post("/api/events/", body, format="json").status_code == 401

    story.mission.location.track.is_active = False
    story.mission.location.track.save()
    student = User.objects.create_user("other", "o@example.com", "S3cure-pass-3")
    api = APIClient()
    api.force_authenticate(student)
    assert api.post("/api/events/", body, format="json").status_code == 404


def test_find_task_ignores_anything_that_is_not_an_id(course):
    _, story, *_ = course
    assert find_task(story.id) == story
    for junk in (None, "1", 1.0, True, [1], {"a": 1}):
        assert find_task(junk) is None


# ── run rate limit (used by the WebSocket runner) ───────────────────────────


def test_run_rate_limit_allows_a_burst_then_refuses():
    assert [allow_code_run(1) for _ in range(6)] == [True] * 5 + [False]
    assert allow_code_run(2) is True  # other users are unaffected


# ── consent ─────────────────────────────────────────────────────────────────


def register(consent=None, username="newbie"):
    body = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "S3cure-pass-4",
    }
    if consent is not None:
        body["research_consent"] = consent
    return APIClient().post("/api/auth/register/", body, format="json")


def test_consent_is_off_unless_the_learner_opts_in():
    assert register().status_code == 201
    profile = User.objects.get(username="newbie").profile
    assert (profile.research_consent, profile.research_consent_at) == (False, None)


def test_consent_given_at_signup_is_stored_with_a_timestamp():
    response = register(consent=True)
    assert response.status_code == 201
    assert "research_consent" not in response.json()
    profile = User.objects.get(username="newbie").profile
    assert profile.research_consent is True
    assert profile.research_consent_at is not None


def test_consent_can_be_given_and_withdrawn_in_the_profile(client, student):
    assert client.get("/api/profile/me/").json()["research_consent"] is False
    granted = client.patch("/api/profile/me/", {"research_consent": True}, format="json")
    assert granted.status_code == 200
    assert granted.json()["research_consent"] is True
    assert granted.json()["research_consent_at"] is not None
    withdrawn = client.patch("/api/profile/me/", {"research_consent": "false"}, format="json")
    assert withdrawn.json()["research_consent"] is False


@pytest.mark.parametrize("junk", ["yes", 1, None, [True]])
def test_junk_consent_is_rejected_and_changes_nothing(client, student, junk):
    response = client.patch("/api/profile/me/", {"research_consent": junk}, format="json")
    assert response.status_code == 400
    student.profile.refresh_from_db()
    assert student.profile.research_consent is False


# ── export ──────────────────────────────────────────────────────────────────


def read(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def two_learners(course):
    """One consenting learner, one not, plus a teacher - all with activity."""
    mission, story, quiz, code = course
    consenting = User.objects.create_user("consenting", "yes@example.com", "S3cure-pass-5")
    consenting.profile.set_research_consent(True)
    consenting.profile.save()
    private = User.objects.create_user("private", "no@example.com", "S3cure-pass-6")
    teacher = User.objects.create_user("teacher", "t@example.com", "S3cure-pass-7", is_staff=True)
    teacher.profile.set_research_consent(True)
    teacher.profile.save()
    for user in (consenting, private, teacher):
        run(user, code, stdout="wrong\n", code="SECRET-LEARNER-CODE")
        run(user, code, stdout="ok\n", code="SECRET-LEARNER-CODE")
        client = APIClient()
        client.force_authenticate(user)
        client.post(f"/api/mission-tasks/{story.id}/submit/", {}, format="json")
    return consenting, private, teacher


def export(tmp_path, *args):
    call_command("export_learning_data", "--out", str(tmp_path), *args, verbosity=0)
    return {p.stem: read(p) for p in tmp_path.glob("*.csv")}


def test_export_contains_only_consenting_learners(tmp_path, two_learners, settings):
    consenting, private, teacher = two_learners
    settings.SECRET_KEY = "unit-test-secret"
    files = export(tmp_path)
    key = "unit-test-secret"
    assert [r["user"] for r in files["users"]] == [pseudonym(consenting.id, key)]
    for name in ("runs", "events", "task_progress", "mission_progress"):
        assert {r["user"] for r in files[name]} == {pseudonym(consenting.id, key)}, name
    assert len(files["runs"]) == 2
    assert [r["attempt_no"] for r in files["runs"]] == ["1", "2"]


def test_export_can_include_everyone_except_staff(tmp_path, two_learners, settings):
    consenting, private, teacher = two_learners
    settings.SECRET_KEY = "unit-test-secret"
    files = export(tmp_path, "--all-users")
    assert {r["user"] for r in files["users"]} == {
        pseudonym(consenting.id, "unit-test-secret"),
        pseudonym(private.id, "unit-test-secret"),
    }
    assert pseudonym(teacher.id, "unit-test-secret") not in {r["user"] for r in files["runs"]}


def test_export_leaks_no_identity_code_or_answers(tmp_path, two_learners):
    export(tmp_path, "--all-users")
    text = "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.csv"))
    for secret in (
        "consenting", "private", "teacher", "example.com",  # identity
        "SECRET-LEARNER-CODE",  # the learner's code
        "expected_output", '"ok"', "correct_answer",  # answer keys
        "S3cure-pass",
    ):
        assert secret not in text, secret


def test_pseudonyms_are_stable_keyed_and_not_the_id():
    assert pseudonym(7, "k") == pseudonym(7, "k")
    assert pseudonym(7, "k") != pseudonym(7, "other")
    assert pseudonym(7, "k") != pseudonym(8, "k")
    assert "7" != pseudonym(7, "k") and len(pseudonym(7, "k")) == 16


def test_export_salt_overrides_the_secret_key(tmp_path, two_learners, settings):
    consenting, *_ = two_learners
    settings.ANALYTICS_EXPORT_SALT = "dedicated-salt"
    files = export(tmp_path)
    assert files["users"][0]["user"] == pseudonym(consenting.id, "dedicated-salt")


# ── retention ───────────────────────────────────────────────────────────────


def age(queryset, days):
    queryset.update(created_at=timezone.now() - timedelta(days=days))


@pytest.fixture
def old_and_new(student, course):
    *_, code = course
    run(student, code, stdout="ok\n")
    run(student, code, stdout="ok\n")
    LearningEvent.objects.create(user=student, event_type="login")
    LearningEvent.objects.create(user=student, event_type="login")
    age(CodeRun.objects.filter(pk=CodeRun.objects.order_by("id").first().pk), 800)
    age(LearningEvent.objects.filter(pk=LearningEvent.objects.order_by("id").first().pk), 800)


def prune(*args):
    out = StringIO()
    call_command("prune_learning_data", *args, stdout=out)
    return out.getvalue()


def test_prune_deletes_only_what_is_older_than_the_limit(old_and_new, student, course):
    *_, code = course
    before = (CodeRun.objects.count(), LearningEvent.objects.count())
    assert prune("--dry-run").count("would delete 1 code run(s) and 1 event(s)") == 1
    assert (CodeRun.objects.count(), LearningEvent.objects.count()) == before

    prune()
    assert CodeRun.objects.count() == before[0] - 1
    assert LearningEvent.objects.count() == before[1] - 1
    # the course state itself is never pruned
    assert TaskProgress.objects.filter(user=student, task=code).exists()


def test_prune_honours_an_explicit_limit_and_rejects_nonsense(old_and_new):
    assert "deleted 0 code run(s)" in prune("--days", "900")
    with pytest.raises(CommandError):
        prune("--days", "0")


# ── the schema is committed ─────────────────────────────────────────────────


def test_no_model_change_is_missing_a_migration():
    call_command("makemigrations", check=True, dry_run=True, verbosity=0)
