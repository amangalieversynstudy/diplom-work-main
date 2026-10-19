"""The teacher's live panel, its measured freshness, and the usability questionnaire (SUS)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.live import FRESHNESS_TARGET_S, MAX_GAP, freshness_summary, live_feed, live_panel
from game.models import (
    CodeRun,
    FreshnessSample,
    LearningEvent,
    Location,
    Mission,
    MissionTask,
    Progress,
    Track,
    UsabilityResponse,
)
from game.pilot import build_report, render_markdown
from game.usability import sus_score, usability_summary, verdict

User = get_user_model()

pytestmark = pytest.mark.django_db


def _course(owner, slug):
    track = Track.objects.create(slug=slug, title=slug.title(), is_active=True, owner=owner)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title=f"{slug} mission", order=1)
    task = MissionTask.objects.create(mission=mission, order=1, task_type="code", title=f"{slug} step")
    return mission, task


@pytest.fixture
def teacher():
    return User.objects.create_user("teacher", "t@example.com", "S3cure-pass-1", is_staff=True)


@pytest.fixture
def other_teacher():
    return User.objects.create_user("other", "o@example.com", "S3cure-pass-1", is_staff=True)


@pytest.fixture
def world(teacher, other_teacher):
    mine = _course(teacher, "mine")
    theirs = _course(other_teacher, "theirs")
    learner = User.objects.create_user("ann", "a@example.com", "S3cure-pass-1")
    Progress.objects.create(user=learner, mission=mine[0], status="in_progress")
    Progress.objects.create(user=learner, mission=theirs[0], status="in_progress")
    return {"mine": mine, "theirs": theirs, "learner": learner}


def _run(user, task, ago=0, **fields):
    run = CodeRun.objects.create(
        user=user, task=task, outcome=fields.pop("outcome", "success"), passed=fields.pop("passed", True),
        attempt_no=1, **fields,
    )
    CodeRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(seconds=ago))
    return run


def _event(user, event_type, task=None, mission=None, ago=0, **meta):
    event = LearningEvent.objects.create(user=user, event_type=event_type, task=task, mission=mission, meta=meta)
    LearningEvent.objects.filter(pk=event.pk).update(created_at=timezone.now() - timedelta(seconds=ago))
    return event


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# ── the live picture ───────────────────────────────────────────────────────


def test_the_panel_counts_who_works_now_and_shows_the_last_things_they_did(teacher, world):
    _run(world["learner"], world["mine"][1], ago=20, passed=False, outcome="error")
    _run(world["learner"], world["mine"][1], ago=5)
    panel = live_panel(teacher)
    assert panel["active_now"] == 1
    assert panel["poll_seconds"] == 10
    kinds = [item["kind"] for item in panel["events"]]
    assert kinds == ["code_ok", "code_fail"]  # newest first
    assert panel["events"][0]["learner"] == "ann" and panel["events"][0]["title"] == "mine step"
    assert all("code" not in item for item in panel["events"])  # never the learner's code


def test_a_learner_who_was_quiet_for_an_hour_is_not_active_now(teacher, world):
    _run(world["learner"], world["mine"][1], ago=3600)
    panel = live_panel(teacher)
    assert panel["active_now"] == 0
    assert panel["last_activity_at"] is not None


def test_the_feed_shows_only_the_viewers_own_courses(teacher, other_teacher, world):
    _run(world["learner"], world["theirs"][1], ago=3)
    _event(world["learner"], LearningEvent.MISSION_STARTED, mission=world["theirs"][0], ago=2)
    assert live_feed(teacher) == []
    assert [item["title"] for item in live_feed(other_teacher)] == ["theirs mission", "theirs step"]


def test_a_teacher_without_learners_gets_an_empty_but_valid_panel(teacher):
    panel = live_panel(teacher)
    assert panel["active_now"] == 0 and panel["events"] == [] and panel["last_activity_at"] is None
    assert panel["freshness"]["samples"] == 0


def test_answers_and_explain_answers_are_told_apart_and_repeats_are_skipped(teacher, world):
    mission, task = world["mine"]
    _event(world["learner"], LearningEvent.TASK_SUBMITTED, task=task, ago=4, correct=True)
    _event(world["learner"], LearningEvent.TASK_SUBMITTED, task=task, ago=3, correct=False, kind="explain")
    _event(world["learner"], LearningEvent.TASK_SUBMITTED, task=task, ago=2, correct=True, after_solved=True)
    assert [item["kind"] for item in live_feed(teacher)] == ["explain_fail", "quiz_ok"]


# ── data freshness is measured ─────────────────────────────────────────────


def test_new_actions_since_the_previous_answer_are_timed(teacher, world):
    now = timezone.now()
    _run(world["learner"], world["mine"][1], ago=6)
    _run(world["learner"], world["mine"][1], ago=2)
    live_panel(teacher, since=now - timedelta(seconds=10), now=now)
    sample = FreshnessSample.objects.get()
    assert sample.viewer == teacher and sample.new_events == 2
    assert 3.5 <= sample.lag_mean_s <= 4.5 and 5.5 <= sample.lag_max_s <= 6.5


def test_an_answer_that_carries_nothing_new_writes_no_sample(teacher, world):
    now = timezone.now()
    _run(world["learner"], world["mine"][1], ago=60)
    live_panel(teacher, since=now - timedelta(seconds=10), now=now)
    assert not FreshnessSample.objects.exists()


def test_without_since_or_after_a_long_silence_nothing_is_measured(teacher, world):
    now = timezone.now()
    _run(world["learner"], world["mine"][1], ago=1)
    live_panel(teacher, now=now)
    live_panel(teacher, since=now - MAX_GAP - timedelta(seconds=5), now=now)  # a hidden tab, a sleeping laptop
    live_panel(teacher, since=now + timedelta(seconds=5), now=now)  # a clock from the future
    assert not FreshnessSample.objects.exists()


def test_the_summary_weights_by_actions_and_counts_samples_within_the_target(teacher):
    now = timezone.now()
    FreshnessSample.objects.create(viewer=teacher, polled_at=now, new_events=1, lag_mean_s=2, lag_max_s=2)
    FreshnessSample.objects.create(viewer=teacher, polled_at=now, new_events=3, lag_mean_s=10, lag_max_s=FRESHNESS_TARGET_S + 5)
    summary = freshness_summary()
    assert summary["samples"] == 2 and summary["events"] == 4
    assert summary["mean_s"] == 8.0  # (1*2 + 3*10) / 4
    assert summary["worst_s"] == FRESHNESS_TARGET_S + 5
    assert summary["within_target_pct"] == 50
    assert freshness_summary(viewer=User.objects.create_user("nobody", "n@example.com", "S3cure-pass-1"))["samples"] == 0


def test_the_api_measures_with_the_since_the_panel_sends(teacher, world):
    first = _api(teacher).get("/api/teacher/live/").json()
    assert first["freshness"]["samples"] == 0
    _run(world["learner"], world["mine"][1], ago=0)  # after the first answer was generated
    again = _api(teacher).get("/api/teacher/live/", {"since": first["generated_at"]}).json()
    assert again["freshness"]["samples"] == 1 and again["freshness"]["events"] == 1
    assert _api(teacher).get("/api/teacher/live/", {"since": "garbage"}).status_code == 200


def test_the_live_endpoint_is_for_teachers_only(world):
    assert _api(world["learner"]).get("/api/teacher/live/").status_code == 403
    assert APIClient().get("/api/teacher/live/").status_code in (401, 403)


# ── usability (SUS) ────────────────────────────────────────────────────────


def test_the_sus_score_follows_the_standard_formula():
    assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100  # the best possible
    assert sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0
    assert sus_score([3] * 10) == 50
    assert sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75


@pytest.mark.parametrize("bad", [None, "x", [3] * 9, [3] * 11, [0] + [3] * 9, [6] + [3] * 9, [True] * 10, [3.5] * 10])
def test_the_sus_score_refuses_answers_that_are_not_ten_ratings(bad):
    with pytest.raises(ValueError):
        sus_score(bad)


def test_the_verdict_uses_the_usual_benchmarks():
    assert (verdict(85), verdict(70), verdict(68), verdict(50), verdict(None)) == ("good", "average", "average", "below_average", None)


def test_a_teacher_rates_the_dashboard_and_only_the_latest_answer_counts(teacher):
    client = _api(teacher)
    assert client.get("/api/teacher/usability/").json() == {"answered_at": None}
    first = client.post("/api/teacher/usability/", {"answers": [3] * 10, "comment": "ok"}, format="json")
    assert first.status_code == 201 and first.json() == {"saved": True}
    assert client.get("/api/teacher/usability/").json()["answered_at"]
    client.post("/api/teacher/usability/", {"answers": [5, 1] * 5}, format="json")
    assert UsabilityResponse.objects.filter(user=teacher).count() == 2
    summary = usability_summary()
    assert summary["respondents"] == 1 and summary["mean"] == 100 and summary["verdict"] == "good"


def test_the_questionnaire_rejects_bad_answers_and_students(teacher, world):
    assert _api(teacher).post("/api/teacher/usability/", {"answers": [3] * 9}, format="json").status_code == 400
    assert _api(teacher).post("/api/teacher/usability/", {"answers": [9] * 10}, format="json").status_code == 400
    assert _api(world["learner"]).post("/api/teacher/usability/", {"answers": [3] * 10}, format="json").status_code == 403
    assert not UsabilityResponse.objects.exists()


def test_a_long_comment_is_cut(teacher):
    _api(teacher).post("/api/teacher/usability/", {"answers": [3] * 10, "comment": "x" * 5000}, format="json")
    assert len(UsabilityResponse.objects.get().comment) == 1000


# ── the pilot report carries both parameters ───────────────────────────────


def test_the_pilot_report_says_how_fresh_the_data_was_and_how_convenient(teacher):
    text = render_markdown(build_report())
    assert "замеров нет" in text and "ответов нет" in text
    FreshnessSample.objects.create(viewer=teacher, polled_at=timezone.now(), new_events=2, lag_mean_s=4, lag_max_s=6)
    UsabilityResponse.objects.create(user=teacher, answers=[3] * 10, score=72.5)
    text = render_markdown(build_report())
    assert "в среднем за **4.0 с**" in text and "100%" in text
    assert "SUS" in text and "72.5" in text and "Ответивших мало" in text


# ── security: a teacher sees activity in their own courses only ────────────


def test_the_live_panel_ignores_activity_in_other_teachers_courses(teacher, world):
    _run(world["learner"], world["theirs"][1], ago=5)  # a run in the other teacher's course
    _run(world["learner"], None, ago=5)  # free practice, no step
    _event(world["learner"], LearningEvent.TASK_OPENED, task=world["theirs"][1], mission=world["theirs"][0], ago=5)
    panel = live_panel(teacher)
    assert panel["active_now"] == 0 and panel["last_activity_at"] is None
    _run(world["learner"], world["mine"][1], ago=5)
    assert live_panel(teacher)["active_now"] == 1


def test_the_student_card_counts_runs_in_the_teachers_courses_only(teacher, world):
    from game.me import my_learning

    for _ in range(2):
        _run(world["learner"], world["mine"][1], ago=60)
    for _ in range(3):
        _run(world["learner"], world["theirs"][1], ago=60)
    _run(world["learner"], None, ago=60)
    own = my_learning(world["learner"], owner=teacher)
    assert sum(day["runs"] for day in own["activity"]) == 2
    assert own["summary"]["days_away"] is not None
    assert sum(day["runs"] for day in my_learning(world["learner"])["activity"]) == 6


def test_a_teacher_without_own_activity_sees_no_last_seen(teacher, world):
    from game.me import my_learning

    _run(world["learner"], world["theirs"][1], ago=60)
    assert my_learning(world["learner"], owner=teacher)["summary"]["days_away"] is None


# ── security: the questionnaire is rate-limited; both pilot answers are kept ─


def test_first_and_last_week_answers_are_kept_and_the_summary_reads_latest_in_the_db(teacher, django_assert_num_queries):
    client = _api(teacher)
    client.post("/api/teacher/usability/", {"answers": [3] * 10}, format="json")
    client.post("/api/teacher/usability/", {"answers": [5, 1] * 5}, format="json")
    assert UsabilityResponse.objects.filter(user=teacher).count() == 2
    with django_assert_num_queries(1):
        latest = __import__("game.usability", fromlist=["x"]).latest_by_user()
    assert latest[teacher.pk].score == 100


def test_the_questionnaire_is_rate_limited(teacher):
    from django.core.cache import cache

    cache.clear()
    client = _api(teacher)
    codes = [client.post("/api/teacher/usability/", {"answers": [3] * 10}, format="json").status_code for _ in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429
    assert client.get("/api/teacher/usability/").status_code == 200
    cache.clear()


# ── pilot integrity: whose answers and panels count ────────────────────────


def test_a_self_registered_teachers_sus_answer_is_not_counted_in_the_pilot(teacher):
    from game.models import UsabilityResponse

    self_service = User.objects.create_user(username="selfie", password="TestPass123!", is_teacher=True)
    UsabilityResponse.objects.create(user=teacher, answers=[5, 1] * 5, score=100)
    UsabilityResponse.objects.create(user=self_service, answers=[1, 5] * 5, score=0)

    summary = usability_summary()
    assert summary["respondents"] == 1 and summary["mean"] == 100
    assert summary["excluded_respondents"] == 1


def test_only_pilot_teachers_can_answer_the_questionnaire(teacher):
    self_service = User.objects.create_user(username="selfie2", password="TestPass123!", is_teacher=True)
    answers = {"answers": [4, 2] * 5}
    assert _api(self_service).post("/api/teacher/usability/", answers, format="json").status_code == 403
    assert _api(teacher).post("/api/teacher/usability/", answers, format="json").status_code == 201


def test_the_pilot_freshness_ignores_panels_of_self_registered_teachers(teacher):
    self_service = User.objects.create_user(username="selfie3", password="TestPass123!", is_teacher=True)
    now = timezone.now()
    for viewer in (teacher, self_service):
        FreshnessSample.objects.create(viewer=viewer, polled_at=now, new_events=1, lag_mean_s=1, lag_max_s=1)
    assert freshness_summary()["samples"] == 1
    assert freshness_summary(viewer=self_service)["samples"] == 1  # their own card is unchanged


def test_a_since_the_server_did_not_issue_is_not_measured(teacher, world):
    first = _api(teacher).get("/api/teacher/live/").json()
    _run(world["learner"], world["mine"][1], ago=0)
    made_up = (timezone.now() - timedelta(seconds=25)).isoformat()
    _api(teacher).get("/api/teacher/live/", {"since": made_up})
    assert FreshnessSample.objects.count() == 0
    assert first["generated_at"]


def test_a_since_is_measured_only_once_and_only_for_its_viewer(teacher, other_teacher, world):
    first = _api(teacher).get("/api/teacher/live/").json()
    _run(world["learner"], world["mine"][1], ago=0)
    _api(other_teacher).get("/api/teacher/live/", {"since": first["generated_at"]})  # borrowed
    assert FreshnessSample.objects.count() == 0
    _api(teacher).get("/api/teacher/live/", {"since": first["generated_at"]})
    _api(teacher).get("/api/teacher/live/", {"since": first["generated_at"]})  # replayed
    assert FreshnessSample.objects.count() == 1


@pytest.mark.parametrize("since", ["2026-13-01T00:00:00+00:00", "2026-10-17T10:00:00+99:00"])
def test_a_malformed_since_is_ignored_not_an_error(teacher, since):
    assert _api(teacher).get("/api/teacher/live/", {"since": since}).status_code == 200
