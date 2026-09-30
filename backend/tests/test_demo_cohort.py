"""seed_demo_cohort: a made-up class that lights up every screen of the teacher."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from game.authorship import authorship_overview
from game.management.commands.seed_demo_cohort import demo_users
from game.models import CodeRun, LearningEvent, LeaderboardEntry, Track
from game.warning import early_warning

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def teacher():
    call_command("seed_course", stdout=io.StringIO())
    user = User.objects.create_user("teacher", "t@example.com", "S3cure-pass-1", is_staff=True)
    Track.objects.update(owner=user)
    return user


def _seed(*args):
    out = io.StringIO()
    call_command("seed_demo_cohort", "--teacher", "teacher", *args, stdout=out)
    return out.getvalue()


def test_a_class_of_the_asked_size_appears_and_cannot_log_in(teacher):
    _seed("--count", "20")
    assert demo_users().count() == 20
    assert all(not user.has_usable_password() for user in demo_users())
    assert all(not user.profile.research_consent for user in demo_users())


def test_running_it_twice_leaves_one_class(teacher):
    _seed("--count", "12")
    _seed("--count", "12")
    assert demo_users().count() == 12


def test_remove_takes_everything_away(teacher):
    _seed("--count", "12")
    call_command("seed_demo_cohort", "--remove", stdout=io.StringIO())
    assert demo_users().count() == 0
    assert not CodeRun.objects.exists() and not LeaderboardEntry.objects.filter(user__username__startswith="demo_").exists()


def test_the_same_seed_makes_the_same_class(teacher):
    _seed("--count", "12", "--seed", "3")
    first = sorted(demo_users().values_list("profile__xp", flat=True))
    _seed("--count", "12", "--seed", "3")
    assert sorted(demo_users().values_list("profile__xp", flat=True)) == first


def test_the_teachers_screens_have_something_to_show(teacher):
    _seed("--count", "24")
    warned = early_warning(teacher)["students"]
    assert warned, "somebody is stuck or gone"
    looked_at = authorship_overview(teacher, limit=50)
    assert looked_at, "somebody pasted solutions or shares one"
    assert LearningEvent.objects.filter(event_type="hint_used").exists()
    assert LeaderboardEntry.objects.filter(user__username__startswith="demo_").exists()


def test_the_pasting_learners_are_the_ones_with_signs(teacher):
    _seed("--count", "30")
    flagged = {row["username"] for row in authorship_overview(teacher, limit=100)}
    pasters = {
        run.user.username
        for run in CodeRun.objects.filter(passed=True).select_related("user")
        if run.provenance.get("pasted_chars", 0) >= 60
    }
    assert pasters and pasters <= flagged


def test_it_refuses_without_a_course_to_play():
    with pytest.raises(CommandError):
        call_command("seed_demo_cohort", "--teacher", "nobody", stdout=io.StringIO())


def test_it_refuses_a_silly_size(teacher):
    with pytest.raises(CommandError):
        _seed("--count", "1")
