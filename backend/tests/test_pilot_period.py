"""The pilot's period and cohort: PILOT_STARTED_AT / PILOT_ENDED_AT, pilot_check, the contact log of pilot_report."""

from datetime import timedelta, timezone as dt_timezone
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from game.cohort import parse_moment, pilot_learners, research_learners
from game.management.commands.pilot_check import FAIL, OK, WARN, check_period, check_settings
from game.models import EarlyWarningSnapshot
from game.pilot import build_report

User = get_user_model()
pytestmark = pytest.mark.django_db


def _learner(name, *, consent=True, joined=None):
    user = User.objects.create_user(username=name, password="TestPass123!")
    if consent:
        user.profile.set_research_consent(True)
        user.profile.save()
    if joined is not None:
        User.objects.filter(pk=user.pk).update(date_joined=joined)
    return user


def _levels(lines):
    return [(level, text) for level, text in lines]


def test_parse_moment_needs_a_time_zone():
    assert parse_moment("2026-11-09T00:00:00+05:00") is not None
    assert parse_moment("2026-11-09") is None  # a bare date would be ignored silently
    assert parse_moment("2026-11-09T00:00:00") is None
    assert parse_moment("") is None and parse_moment("soon") is None


def test_the_cohort_is_who_signed_up_since_the_start(settings):
    start = timezone.now() - timedelta(days=3)
    _learner("rehearsal", joined=start - timedelta(days=2))
    _learner("pilot", joined=start + timedelta(hours=2))
    _learner("shy", consent=False, joined=start + timedelta(hours=3))
    assert research_learners().count() == 2 and pilot_learners().count() == 3
    settings.PILOT_STARTED_AT = start.isoformat()
    assert list(research_learners().values_list("username", flat=True)) == ["pilot"]
    assert pilot_learners().count() == 2
    report = build_report()
    assert report["participants"]["learners"] == 2 and report["participants"]["consented"] == 1


@pytest.mark.parametrize(
    "start, end, expected",
    [
        ("2026-11-09", "", FAIL),  # a bare date
        ("2026-11-09T00:00:00+05:00", "2026-11-01T00:00:00+05:00", FAIL),  # end before start
        ("2026-11-09T00:00:00+05:00", "2026-12-21", FAIL),  # end without a zone
    ],
)
def test_pilot_check_rejects_dates_it_would_ignore(settings, start, end, expected):
    settings.PILOT_STARTED_AT, settings.PILOT_ENDED_AT = start, end
    assert expected in [level for level, _ in check_period(now=timezone.now())]


def test_pilot_check_warns_about_a_missing_snapshot_while_the_pilot_runs(settings):
    now = timezone.now()
    settings.PILOT_STARTED_AT = (now - timedelta(days=5)).isoformat()
    settings.PILOT_ENDED_AT = (now + timedelta(days=30)).isoformat()
    messages = dict(_levels(check_period(now=now)))
    assert WARN in messages and "Снимка списка" in messages[WARN]
    user = _learner("a")
    EarlyWarningSnapshot.objects.create(
        date=(now.astimezone(dt_timezone.utc) - timedelta(days=1)).date(), user=user, level="ok", score=0
    )
    lines = list(check_period(now=now))
    assert (OK, f"Снимок списка за {(now.astimezone(dt_timezone.utc) - timedelta(days=1)).date()} записан.") in lines
    assert all(level != FAIL for level, _ in lines)


def test_pilot_check_warns_when_the_model_is_on_during_the_pilot(settings):
    settings.RISK_MODEL_PATH = "/app/risk_model/model.json"
    assert any(level == WARN and "RISK_MODEL_PATH" in text for level, text in check_settings())


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_pilot_report_reads_the_contact_log(tmp_path):
    helped = _learner("helped")
    log = _write(tmp_path / "contacts.csv", "username,date\nhelped,2026-11-20\nhelped,2026-11-18\nnobody,2026-11-19\n")
    out, err = StringIO(), StringIO()
    call_command("pilot_report", "--contacts", log, stdout=out, stderr=err)
    assert "H3 без дней после контакта" in out.getvalue()
    assert "nobody" in err.getvalue()
    from game.management.commands.pilot_report import read_contacts

    first, unknown = read_contacts(log)
    assert first == {helped.pk: __import__("datetime").date(2026, 11, 18)} and unknown == ["nobody"]


def test_pilot_report_rejects_a_bad_date_in_the_contact_log(tmp_path):
    _learner("helped")
    log = _write(tmp_path / "contacts.csv", "username,date\nhelped,вчера\n")
    with pytest.raises(CommandError):
        call_command("pilot_report", "--contacts", log, stdout=StringIO())


def test_the_report_shows_the_period_and_the_pre_registered_metric():
    out = StringIO()
    call_command("pilot_report", stdout=out)
    text = out.getvalue()
    assert "Период пилота" in text and "## H3" in text
