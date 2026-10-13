"""Who solved a code step: the platform's own help (exact) and the editor's signals (hints only)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from game.authorship import authorship_report, clean_provenance, signals_for
from game.footprint import finish_code_run
from game.models import CodeRun, LearningEvent, Location, Mission, MissionTask, Progress, Track

User = get_user_model()

pytestmark = pytest.mark.django_db

CODE = "total = 0\nfor i in range(3):\n    total += i\nprint('ok')\n" * 4  # about 200 characters


@pytest.fixture
def teacher():
    return User.objects.create_user("teacher", "t@example.com", "S3cure-pass-1", is_staff=True)


@pytest.fixture
def student():
    return User.objects.create_user("student", "s@example.com", "S3cure-pass-1")


@pytest.fixture
def step(teacher, student):
    track = Track.objects.create(slug="mine", title="Mine", is_active=True, owner=teacher)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    task = MissionTask.objects.create(
        mission=mission, order=1, task_type="code", title="Loop", data={"expected_output": "ok"}
    )
    Progress.objects.create(user=student, mission=mission, status="in_progress")
    return task


def solve(student, task, provenance=None, code=CODE):
    verdict = finish_code_run(
        student, task, code=code, stdout="ok", stderr="", exit_code=0, duration=0.1,
        reasons=set(), provenance=provenance,
    )
    assert verdict["passed"]
    return CodeRun.objects.filter(user=student, task=task, passed=True).earliest("created_at")


def typed(chars=len(CODE), seconds=240):
    return {"typed_chars": chars, "pasted_chars": 0, "paste_count": 0, "edit_events": chars,
            "edits_after_paste": 0, "elapsed_ms": seconds * 1000}


def pasted(chars=len(CODE), edits=0):
    return {"typed_chars": 0, "pasted_chars": chars, "paste_count": 1, "edit_events": edits,
            "edits_after_paste": edits, "elapsed_ms": 9000}


# ── what the editor may send ────────────────────────────────────────────────


def test_only_known_numeric_fields_survive_and_are_clamped():
    raw = {"pasted_chars": 12.9, "typed_chars": -5, "paste_count": True, "evil": 1, "elapsed_ms": 10**12, "edit_events": "3"}
    assert clean_provenance(raw) == {"pasted_chars": 12, "typed_chars": 0, "elapsed_ms": 10_000_000}


@pytest.mark.parametrize("raw", [None, "x", [], 5])
def test_anything_that_is_not_a_dict_is_dropped(raw):
    assert clean_provenance(raw) == {}


def test_the_run_keeps_counts_and_never_the_code(student, step):
    run = solve(student, step, typed())
    assert run.provenance["typed_chars"] == len(CODE)
    assert CODE not in str(run.provenance)


# ── signals ────────────────────────────────────────────────────────────────


def test_typed_code_raises_nothing(student, step):
    assert signals_for(solve(student, step, typed())) == []


def test_a_pasted_solution_run_without_edits_is_flagged(student, step):
    signals = signals_for(solve(student, step, pasted()))
    assert [s["code"] for s in signals] == ["paste_then_run"]
    assert signals[0]["share"] == 100


def test_a_pasted_solution_that_was_reworked_is_a_weaker_signal(student, step):
    signals = signals_for(solve(student, step, pasted(edits=30)))
    assert [s["code"] for s in signals] == ["large_paste"]


def test_a_small_paste_is_normal(student, step):
    assert signals_for(solve(student, step, pasted(chars=20))) == []


def test_superhuman_typing_speed_is_flagged(student, step):
    signals = signals_for(solve(student, step, typed(chars=200, seconds=5)))
    assert [s["code"] for s in signals] == ["fast_typing"]


def test_a_run_without_editor_data_says_so(student, step):
    assert signals_for(solve(student, step, None)) == [{"code": "no_editor_data"}]


# ── the platform's own help ────────────────────────────────────────────────


def _event(student, task, kind, when=None):
    event = LearningEvent.objects.create(user=student, event_type=kind, task=task)
    if when:
        LearningEvent.objects.filter(pk=event.pk).update(created_at=when)


def test_no_help_means_independent(student, step, teacher):
    solve(student, step, typed())
    report = authorship_report(student, teacher)
    assert report["steps"][0]["assistance"] == "independent"
    assert report["summary"] == {"solved": 1, "independent": 1, "assisted": 0, "flagged": 0}


def test_the_strongest_help_before_the_solve_counts(student, step, teacher):
    _event(student, step, LearningEvent.HINT_USED)
    _event(student, step, LearningEvent.HINT_USED)
    _event(student, step, LearningEvent.AI_MENTOR_USED)
    solve(student, step, typed())
    row = authorship_report(student, teacher)["steps"][0]
    assert row["assistance"] == "mentor"
    assert row["help_uses"] == {"hint": 2, "skeleton": 0, "mentor": 1}


def test_the_free_rescue_hint_is_platform_help(student, step, teacher):
    _event(student, step, LearningEvent.HELP_RESCUE)
    solve(student, step, typed())
    row = authorship_report(student, teacher)["steps"][0]
    assert row["assistance"] == "hint" and row["help_uses"]["hint"] == 1


def test_help_used_after_the_solve_does_not_count(student, step, teacher):
    solve(student, step, typed())
    _event(student, step, LearningEvent.SKELETON_USED, when=timezone.now() + timedelta(minutes=5))
    assert authorship_report(student, teacher)["steps"][0]["assistance"] == "independent"


def test_help_on_another_step_does_not_count(student, step, teacher):
    other = MissionTask.objects.create(mission=step.mission, order=2, task_type="code", title="Other")
    _event(student, other, LearningEvent.SKELETON_USED)
    solve(student, step, typed())
    assert authorship_report(student, teacher)["steps"][0]["assistance"] == "independent"


def test_only_the_solving_run_is_judged(student, step, teacher):
    finish_code_run(student, step, code="print('no')", stdout="no", stderr="", exit_code=0,
                    duration=0.1, reasons=set(), provenance=pasted())
    solve(student, step, typed())
    row = authorship_report(student, teacher)["steps"][0]
    assert row["signals"] == [] and row["attempts"] == 2


def test_an_unsolved_step_is_not_reported(student, step, teacher):
    assert authorship_report(student, teacher)["steps"] == []


# ── who may look ───────────────────────────────────────────────────────────


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _url(student):
    return f"/api/teacher/students/{student.pk}/authorship/"


def test_the_teacher_gets_the_report(student, step, teacher):
    solve(student, step, pasted())
    response = _api(teacher).get(_url(student))
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["summary"]["flagged"] == 1
    assert data["steps"][0]["signals"][0]["code"] == "paste_then_run"
    assert data["steps"][0]["title"] == "Loop"


def test_another_teachers_student_is_a_404(student, step):
    stranger = User.objects.create_user("other", "o@example.com", "S3cure-pass-1", is_staff=True)
    solve(student, step, typed())
    assert _api(stranger).get(_url(student)).status_code == 404


def test_a_student_cannot_read_the_report(student, step):
    assert _api(student).get(_url(student)).status_code == 403


def test_anonymous_is_refused(student, step):
    assert APIClient().get(_url(student)).status_code in (401, 403)


def test_the_research_export_carries_the_counts_for_consenting_learners(student, step, tmp_path):
    import csv

    from django.core.management import call_command

    student.profile.research_consent = True
    student.profile.save()
    solve(student, step, pasted())
    call_command("export_learning_data", out=str(tmp_path))
    with open(tmp_path / "runs.csv", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["pasted_chars"] == str(len(CODE))
    assert rows[0]["paste_count"] == "1"
    assert "code" not in rows[0]


# ── what the code is made of ───────────────────────────────────────────────

OWN = "total = 0\nfor n in range(5):\n    total += n\n    if total > 3:\n        total -= 1\nprint('ok', total, n, len(str(total)))\n"


def test_a_construct_the_author_marked_as_untaught_is_reported(student, step, teacher):
    step.data = {**step.data, "not_yet": ["comprehension", "lambda"]}
    step.save()
    solve(student, step, typed(), code="print('ok')\nsquares = [i * i for i in range(3)]\n")
    row = authorship_report(student, teacher)["steps"][0]
    assert {"code": "untaught_construct", "constructs": "comprehension"} in row["signals"]


def test_a_taught_construct_is_not_reported(student, step, teacher):
    step.data = {**step.data, "not_yet": ["class"]}
    step.save()
    solve(student, step, typed(), code="print('ok')\nsquares = [i * i for i in range(3)]\n")
    assert authorship_report(student, teacher)["steps"][0]["signals"] == []


def _second_student(step, name, code):
    other = User.objects.create_user(name, f"{name}@example.com", "S3cure-pass-1")
    Progress.objects.create(user=other, mission=step.mission, status="in_progress")
    solve(other, step, typed(), code=code)
    return other


def test_the_same_structure_as_another_learner_is_reported_despite_renaming(student, step, teacher):
    friend_code = OWN.replace("total", "acc")
    _second_student(step, "friend", friend_code)
    solve(student, step, typed(), code=OWN)
    signals = authorship_report(student, teacher)["steps"][0]["signals"]
    same = [s for s in signals if s["code"] == "same_as_others"]
    assert same == [{"code": "same_as_others", "count": 1, "with": "friend"}]


def test_small_solutions_are_not_compared(student, step, teacher):
    _second_student(step, "friend", "print('ok')\n")
    solve(student, step, typed(), code="print('ok')\n")
    assert authorship_report(student, teacher)["steps"][0]["signals"] == []


def test_a_different_solution_is_not_a_twin(student, step, teacher):
    _second_student(step, "friend", OWN)
    solve(student, step, typed(), code=OWN.replace("total -= 1", "total -= 2"))
    assert all(s["code"] != "same_as_others" for s in authorship_report(student, teacher)["steps"][0]["signals"])


def test_learners_of_another_teacher_are_never_named(student, step, teacher):
    other_teacher = User.objects.create_user("t2", "t2@example.com", "S3cure-pass-1", is_staff=True)
    track = Track.objects.create(slug="theirs", title="T", is_active=True, owner=other_teacher)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    theirs = MissionTask.objects.create(mission=mission, order=1, task_type="code", data={"expected_output": "ok"})
    stranger = User.objects.create_user("stranger", "st@example.com", "S3cure-pass-1")
    Progress.objects.create(user=stranger, mission=mission, status="in_progress")
    # same structure, but another step and another teacher's course: nothing to report
    solve(stranger, theirs, typed(), code=OWN)
    solve(student, step, typed(), code=OWN)
    assert authorship_report(student, teacher)["steps"][0]["signals"] == []


def test_the_run_stores_the_analysis_and_not_the_code(student, step):
    run = solve(student, step, typed(), code=OWN)
    assert len(run.fingerprint) == 32 and run.ast_nodes > 20 and run.constructs == []


def _variant_step(step):
    step.data = {**step.data, "variants": [{"vars": {"n": 1}, "expected_output": "ok"}, {"vars": {"n": 2}, "expected_output": "ok"}]}
    step.save()


def _friend_with_variant(step, same_as, name):
    from game.variants import variant_index

    want = variant_index(same_as.pk, step.pk, 2)
    for i in range(200):
        other = User.objects.create_user(f"{name}{i}", f"{name}{i}@example.com", "S3cure-pass-1")
        if (variant_index(other.pk, step.pk, 2) == want) == name.startswith("same"):
            Progress.objects.create(user=other, mission=step.mission, status="in_progress")
            solve(other, step, typed(), code=OWN)
            return other
        other.delete()
    raise AssertionError("no friend found")


def test_identical_solutions_of_the_same_variant_are_expected_not_suspicious(student, step, teacher):
    _variant_step(step)
    _friend_with_variant(step, student, "same")
    solve(student, step, typed(), code=OWN)
    assert all(s["code"] != "same_as_others" for s in authorship_report(student, teacher)["steps"][0]["signals"])


def test_identical_solutions_of_different_variants_are_reported(student, step, teacher):
    _variant_step(step)
    _friend_with_variant(step, student, "other")
    solve(student, step, typed(), code=OWN)
    assert any(s["code"] == "same_as_others" for s in authorship_report(student, teacher)["steps"][0]["signals"])


# ── where to look first ────────────────────────────────────────────────────


def test_the_overview_lists_only_learners_with_signs_most_first(student, step, teacher):
    from game.authorship import authorship_overview

    solve(student, step, pasted())  # a pasted solution
    calm = User.objects.create_user("calm", "calm@example.com", "S3cure-pass-1")
    Progress.objects.create(user=calm, mission=step.mission, status="in_progress")
    solve(calm, step, typed(chars=13), code="print('ok')\n")
    rows = authorship_overview(teacher)
    assert [(r["username"], r["flagged"], r["solved"]) for r in rows] == [("student", 1, 1)]


def test_the_overview_endpoint_is_for_teachers_and_scoped(student, step, teacher):
    solve(student, step, pasted())
    response = _api(teacher).get("/api/teacher/authorship/")
    assert response.status_code == 200
    assert [r["username"] for r in response.json()["students"]] == ["student"]
    stranger = User.objects.create_user("t3", "t3@example.com", "S3cure-pass-1", is_staff=True)
    assert _api(stranger).get("/api/teacher/authorship/").json() == {"students": []}
    assert _api(student).get("/api/teacher/authorship/").status_code == 403
    assert APIClient().get("/api/teacher/authorship/").status_code in (401, 403)
