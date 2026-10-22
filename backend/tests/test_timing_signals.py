"""Time on step and pauses: provenance keys, the two timing signals, report timing, median solve time."""

import pytest
from django.contrib.auth import get_user_model

from game.authorship import authorship_report, clean_provenance, signals_for
from game.metrics import compute_metrics
from game.models import Progress

from tests.test_authorship import CODE, pasted, solve, step, student, teacher, typed  # noqa: F401

User = get_user_model()
pytestmark = pytest.mark.django_db

NEW = ("active_ms", "away_ms", "away_count", "longest_away_ms", "pause_count",
       "longest_pause_ms", "first_key_ms", "paste_after_away")


def codes(run):
    return [s["code"] for s in signals_for(run)]


def test_new_keys_are_clamped_and_unknown_dropped():
    raw = {k: 5 for k in NEW}
    raw.update(active_ms=-3, away_ms=10**12, secret="x", keys="abc")
    out = clean_provenance(raw)
    assert out["active_ms"] == 0 and out["away_ms"] == 10_000_000
    assert out["pause_count"] == 5 and "secret" not in out and "keys" not in out
    assert set(out) == set(NEW)


def test_fast_solve_boundaries(student, step):
    run = solve(student, step, typed(seconds=19))
    assert "fast_solve" in codes(run)
    sig = [s for s in signals_for(run) if s["code"] == "fast_solve"][0]
    # "chars" is what the learner added (typed + pasted), not the length of the whole code
    assert sig == {"code": "fast_solve", "seconds": 19, "chars": run.provenance["typed_chars"]}


def test_fast_solve_not_at_20s(student, step):
    assert "fast_solve" not in codes(solve(student, step, typed(seconds=20)))


def test_fast_solve_not_for_zero_elapsed_or_few_added_chars(student, step):
    run = solve(student, step, typed(seconds=0))
    assert "fast_solve" not in codes(run)
    run.provenance = typed(chars=79, seconds=5)
    assert "fast_solve" not in codes(run)
    run.provenance = typed(chars=80, seconds=5)
    assert "fast_solve" in codes(run)


def test_fast_solve_ignores_the_starter_code(student, step):
    """A long starter code the learner only touched up must not look like a solution written in seconds."""
    run = solve(student, step, typed(chars=12, seconds=6))
    assert run.code_length >= 80
    assert "fast_solve" not in codes(run)
    run.provenance = dict(pasted(chars=90), typed_chars=10)
    assert "fast_solve" in codes(run)


def test_away_then_paste_boundaries(student, step):
    base = dict(pasted(chars=40), paste_after_away=1)
    run = solve(student, step, base)
    sig = [s for s in signals_for(run) if s["code"] == "away_then_paste"]
    assert sig == [{"code": "away_then_paste", "count": 1}]
    run.provenance = dict(base, pasted_chars=39)
    assert "away_then_paste" not in codes(run)
    run.provenance = dict(base, paste_after_away=0)
    assert "away_then_paste" not in codes(run)


def test_no_new_signal_without_editor_data(student, step):
    assert signals_for(solve(student, step, None)) == [{"code": "no_editor_data"}]


def test_report_timing_present_and_null(student, step, teacher):
    prov = dict(typed(seconds=240), active_ms=200_400, away_ms=30_000, away_count=2,
                pause_count=3, longest_pause_ms=45_000, first_key_ms=7_000, longest_away_ms=20_000)
    solve(student, step, prov)
    timing = authorship_report(student, teacher)["steps"][0]["timing"]
    assert timing == {"elapsed_s": 240, "active_s": 200, "away_s": 30, "away_count": 2,
                      "pause_count": 3, "longest_pause_s": 45, "first_key_s": 7}


def test_report_timing_old_run_has_nulls_and_missing_data_is_null(student, step, teacher):
    solve(student, step, typed(seconds=240))
    timing = authorship_report(student, teacher)["steps"][0]["timing"]
    assert timing["elapsed_s"] == 240 and timing["active_s"] is None and timing["away_count"] is None


def test_report_timing_null_without_provenance(student, step, teacher):
    solve(student, step, None)
    assert authorship_report(student, teacher)["steps"][0]["timing"] is None


def _learners(step, seconds):
    for i, sec in enumerate(seconds):
        user = User.objects.create_user(f"l{i}", f"l{i}@example.com", "S3cure-pass-1")
        Progress.objects.create(user=user, mission=step.mission, status="in_progress")
        prov = dict(typed(seconds=sec + 50), active_ms=sec * 1000)
        solve(user, step, prov, code=CODE + f"# {i}\n")


def _row(viewer, step):
    return [r for r in compute_metrics(viewer)["tasks"] if r["task_id"] == step.pk][0]


def test_median_with_three_runs_and_null_with_two(step, teacher):
    _learners(step, [100, 300])
    row = _row(teacher, step)
    assert row["median_solve_s"] is None and row["median_solve_n"] == 2
    _learners_extra = User.objects.create_user("l9", "l9@example.com", "S3cure-pass-1")
    Progress.objects.create(user=_learners_extra, mission=step.mission, status="in_progress")
    solve(_learners_extra, step, dict(typed(seconds=900), active_ms=200_000))
    row = _row(teacher, step)
    assert row["median_solve_s"] == 200 and row["median_solve_n"] == 3


def test_median_is_not_visible_to_another_teacher(step):
    _learners(step, [100, 200, 300])
    other = User.objects.create_user("other", "o@example.com", "S3cure-pass-1", is_staff=True)
    assert not [r for r in compute_metrics(other)["tasks"] if r["task_id"] == step.pk]
