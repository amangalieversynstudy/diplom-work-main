"""The tavern: friends, the friends' leaderboard, item exchange, guilds and quiz duels.

Nothing in the tavern pays XP or writes learning events; it is for players only (teachers are not players)
and the server can switch it off.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import LeaderboardEntry, LearningEvent, Location, Mission, MissionTask, Progress, Track
from social import services
from social.models import Duel, DuelAttempt, Friendship, Guild, GuildMembership, ItemTrade

User = get_user_model()

pytestmark = pytest.mark.django_db


def _player(name, **profile):
    user = User.objects.create_user(name, f"{name}@example.com", "S3cure-pass-1")
    for field, value in profile.items():
        setattr(user.profile, field, value)
    user.profile.save()
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _befriend(a, b):
    assert services.request_friend(a, b) == "pending"
    assert services.request_friend(b, a) == "accepted"


@pytest.fixture
def ann():
    return _player("ann", hint_scrolls=5, skeleton_scrolls=3, xp=250, level=3)


@pytest.fixture
def bob():
    return _player("bob", hint_scrolls=2, skeleton_scrolls=4, xp=120, level=2)


# ── friends ──────────────────────────────────────────────────────────────────


def test_a_request_answered_by_a_request_makes_friends(ann, bob):
    api = _client(ann)
    sent = api.post("/api/social/friends/", {"username": "BOB"}, format="json")  # any letter case
    assert sent.status_code == 201, sent.content
    assert sent.json()["outgoing"][0]["username"] == "bob"
    incoming = _client(bob).get("/api/social/friends/").json()["incoming"]
    assert [card["username"] for card in incoming] == ["ann"]

    answered = _client(bob).post("/api/social/friends/", {"username": "ann"}, format="json")
    assert answered.status_code == 200
    assert answered.json()["status"] == "accepted"
    assert [card["username"] for card in answered.json()["friends"]] == ["ann"]
    assert Friendship.objects.count() == 1  # one row per pair whoever asked


def test_accept_and_remove(ann, bob):
    services.request_friend(ann, bob)
    accepted = _client(bob).post(f"/api/social/friends/{ann.pk}/accept/")
    assert accepted.status_code == 200
    assert services.are_friends(ann, bob)
    # the one who asked cannot accept their own request
    assert _client(ann).post(f"/api/social/friends/{bob.pk}/accept/").status_code == 404

    removed = _client(ann).delete(f"/api/social/friends/{bob.pk}/")
    assert removed.status_code == 200
    assert not Friendship.objects.exists()


def test_unknown_self_and_teacher_targets_are_refused(ann):
    teacher = User.objects.create_user("teach", "t@example.com", "S3cure-pass-1", is_teacher=True)
    api = _client(ann)
    assert api.post("/api/social/friends/", {"username": "nobody"}, format="json").status_code == 404
    assert api.post("/api/social/friends/", {"username": "teach"}, format="json").status_code == 404
    assert api.post("/api/social/friends/", {"username": "ann"}, format="json").status_code == 400
    # and a teacher cannot use the tavern at all (preview mode: their items are free)
    assert _client(teacher).get("/api/social/friends/").status_code == 403


def test_anonymous_and_switched_off(ann):
    assert APIClient().get("/api/social/friends/").status_code == 401
    with override_settings(SOCIAL_ENABLED=False):
        assert _client(ann).get("/api/social/friends/").status_code == 404
        assert _client(ann).get("/api/profile/me/").json()["social_enabled"] is False


def test_friends_leaderboard_lists_me_and_my_friends_only(ann, bob):
    carl = _player("carl", xp=900, level=10)
    for user, xp in ((ann, 250), (bob, 120), (carl, 900)):
        LeaderboardEntry.objects.create(user=user, scope="global", period_label="all_time", xp_total=xp)
    _befriend(ann, bob)

    rows = _client(ann).get("/api/leaderboard/", {"scope": "friends"}).json()
    assert [row["username"] for row in rows] == ["ann", "bob"]
    # a guest has no friends
    assert APIClient().get("/api/leaderboard/", {"scope": "friends"}).json() == []


# ── item exchange ────────────────────────────────────────────────────────────


def test_a_gift_moves_items_when_accepted(ann, bob):
    _befriend(ann, bob)
    offer = _client(ann).post(
        "/api/social/trades/", {"to": "bob", "give_item": "hint_scrolls", "give_qty": 2}, format="json"
    )
    assert offer.status_code == 201, offer.content
    trade = ItemTrade.objects.get()
    ann.profile.refresh_from_db()
    assert ann.profile.hint_scrolls == 5  # nothing moves before the answer

    accepted = _client(bob).post(f"/api/social/trades/{trade.pk}/accept/")
    assert accepted.status_code == 200, accepted.content
    ann.profile.refresh_from_db()
    bob.profile.refresh_from_db()
    assert (ann.profile.hint_scrolls, bob.profile.hint_scrolls) == (3, 4)
    assert accepted.json()["inventory"]["hint_scrolls"] == 4
    assert not LearningEvent.objects.exists()


def test_a_swap_is_all_or_nothing(ann, bob):
    _befriend(ann, bob)
    trade = services.create_trade(ann, bob, "hint_scrolls", 2, "skeleton_scrolls", 3)
    bob.profile.skeleton_scrolls = 1  # bob spent them in the meantime
    bob.profile.save()

    failed = _client(bob).post(f"/api/social/trades/{trade.pk}/accept/")
    assert failed.status_code == 409
    assert failed.json()["code"] == "receiver_short"
    ann.profile.refresh_from_db()
    bob.profile.refresh_from_db()
    assert (ann.profile.hint_scrolls, bob.profile.hint_scrolls, bob.profile.skeleton_scrolls) == (5, 2, 1)
    trade.refresh_from_db()
    assert trade.status == ItemTrade.PENDING

    bob.profile.skeleton_scrolls = 3
    bob.profile.save()
    assert _client(bob).post(f"/api/social/trades/{trade.pk}/accept/").status_code == 200
    ann.profile.refresh_from_db()
    bob.profile.refresh_from_db()
    assert (ann.profile.hint_scrolls, ann.profile.skeleton_scrolls) == (3, 6)
    assert (bob.profile.hint_scrolls, bob.profile.skeleton_scrolls) == (4, 0)


def test_exchange_rules(ann, bob):
    api = _client(ann)
    offer = {"to": "bob", "give_item": "hint_scrolls", "give_qty": 1}
    assert api.post("/api/social/trades/", offer, format="json").status_code == 403  # not friends yet
    _befriend(ann, bob)
    ai = {**offer, "give_item": "ai_summons"}
    assert api.post("/api/social/trades/", ai, format="json").json()["code"] == "bad_item"  # paid quota
    too_many = {**offer, "give_qty": 6}
    assert api.post("/api/social/trades/", too_many, format="json").json()["code"] == "bad_quantity"
    more_than_owned = {**offer, "give_item": "skeleton_scrolls", "give_qty": 4}
    assert api.post("/api/social/trades/", more_than_owned, format="json").status_code == 409

    trade = services.create_trade(ann, bob, "hint_scrolls", 1)
    assert _client(ann).post(f"/api/social/trades/{trade.pk}/accept/").status_code == 404  # not the receiver
    assert _client(bob).post(f"/api/social/trades/{trade.pk}/decline/").status_code == 200
    trade.refresh_from_db()
    assert trade.status == ItemTrade.DECLINED

    other = services.create_trade(ann, bob, "hint_scrolls", 1)
    assert _client(ann).post(f"/api/social/trades/{other.pk}/cancel/").status_code == 200
    other.refresh_from_db()
    assert other.status == ItemTrade.CANCELLED


def test_unfriending_closes_open_offers(ann, bob):
    _befriend(ann, bob)
    trade = services.create_trade(ann, bob, "hint_scrolls", 1)
    services.remove_friend(bob, ann)
    trade.refresh_from_db()
    assert trade.status == ItemTrade.CANCELLED


def test_daily_exchange_limit(ann, bob, monkeypatch):
    _befriend(ann, bob)
    monkeypatch.setattr(services, "MAX_TRADES_PER_DAY", 1)
    first = services.create_trade(ann, bob, "hint_scrolls", 1)
    services.accept_trade(bob, first.pk)
    second = services.create_trade(ann, bob, "hint_scrolls", 1)
    response = _client(bob).post(f"/api/social/trades/{second.pk}/accept/")
    assert response.status_code == 429
    assert response.json()["code"] == "daily_limit"


# ── guilds ───────────────────────────────────────────────────────────────────


def test_found_join_leave_and_rank_guilds(ann, bob):
    founded = _client(ann).post(
        "/api/social/guilds/", {"name": "  Совы   Кода ", "motto": "Думай, потом пиши", "emblem": "owl"}, format="json"
    )
    assert founded.status_code == 201, founded.content
    guild = Guild.objects.get()
    assert guild.name == "Совы Кода" and guild.leader == ann and guild.emblem == "owl"

    duplicate = _client(bob).post("/api/social/guilds/", {"name": "совы кода"}, format="json")
    assert duplicate.json()["code"] == "name_taken"

    joined = _client(bob).post(f"/api/social/guilds/{guild.pk}/join/")
    assert joined.status_code == 200
    assert [m["username"] for m in joined.json()["members_list"]] == ["ann", "bob"]

    listing = _client(bob).get("/api/social/guilds/").json()
    assert listing["mine"] == guild.pk
    assert listing["guilds"][0]["total_xp"] == 370 and listing["guilds"][0]["members"] == 2

    # the leader leaves: the oldest member leads now; the last one out dissolves the guild
    assert _client(ann).post("/api/social/guilds/leave/").status_code == 200
    guild.refresh_from_db()
    assert guild.leader == bob
    assert _client(bob).post("/api/social/guilds/leave/").status_code == 200
    assert not Guild.objects.exists()


def test_guild_rules(ann, bob, monkeypatch):
    newbie = _player("newbie")  # level 1
    assert _client(newbie).post("/api/social/guilds/", {"name": "Новички"}, format="json").status_code == 403
    assert _client(ann).post("/api/social/guilds/", {"name": "<b>x</b>"}, format="json").json()["code"] == "bad_name"
    guild = services.create_guild(ann, "Драконы")
    assert _client(ann).post("/api/social/guilds/", {"name": "Ещё одна"}, format="json").json()["code"] == "in_guild"

    monkeypatch.setattr(services, "GUILD_MAX_MEMBERS", 1)
    assert _client(bob).post(f"/api/social/guilds/{guild.pk}/join/").json()["code"] == "guild_full"
    monkeypatch.setattr(services, "GUILD_MAX_MEMBERS", 20)
    services.join_guild(bob, guild.pk)
    # only the leader removes members
    assert _client(bob).post(f"/api/social/guilds/{guild.pk}/kick/", {"user_id": ann.pk}, format="json").status_code == 403
    assert _client(ann).post(f"/api/social/guilds/{guild.pk}/kick/", {"user_id": bob.pk}, format="json").status_code == 200
    assert not GuildMembership.objects.filter(user=bob).exists()


# ── duels ────────────────────────────────────────────────────────────────────


@pytest.fixture
def quizzes():
    track = Track.objects.create(slug="py", title="Python", is_active=True, is_public=True)
    location = Location.objects.create(track=track, title="L", order=1)
    mission = Mission.objects.create(location=location, title="M", order=1)
    tasks = []
    for n in range(6):
        tasks.append(
            MissionTask.objects.create(
                mission=mission,
                order=n,
                task_type="quiz",
                body_ru=f"<p>Вопрос {n}</p>",
                data={"correct_answer": f"a{n}", "options": [{"value": f"a{n}", "label": "A"}, {"value": "z", "label": "Z"}]},
            )
        )
    explain = MissionTask.objects.create(
        mission=mission, order=10, task_type="quiz",
        data={"kind": "explain", "correct_answer": "x", "options": [{"value": "x"}, {"value": "y"}]},
    )
    varied = MissionTask.objects.create(
        mission=mission, order=11, task_type="quiz",
        data={"correct_answer": "1", "options": [{"value": "1"}, {"value": "2"}], "variants": [{"a": 1}, {"a": 2}]},
    )
    closed = Track.objects.create(slug="closed", title="Class", is_active=True, is_public=False)
    hidden = MissionTask.objects.create(
        mission=Mission.objects.create(location=Location.objects.create(track=closed, title="C"), title="C"),
        task_type="quiz",
        data={"correct_answer": "q", "options": [{"value": "q"}, {"value": "w"}]},
    )
    return {"mission": mission, "tasks": tasks, "excluded": {explain.pk, varied.pk, hidden.pk}}


def _answers(duel, right):
    """Right answers for the first *right* questions of the duel, wrong for the rest."""
    keys = {}
    for n, pk in enumerate(duel.task_ids):
        task = MissionTask.objects.get(pk=pk)
        keys[str(pk)] = task.data["correct_answer"] if n < right else "z"
    return keys


def test_duel_questions_are_shared_plain_quizzes_without_keys(ann, bob, quizzes):
    _befriend(ann, bob)
    Progress.objects.create(user=ann, mission=quizzes["mission"], completed=True)
    created = _client(ann).post("/api/social/duels/", {"username": "bob"}, format="json")
    assert created.status_code == 201, created.content
    duel = Duel.objects.get()
    assert len(duel.task_ids) == 5 and len(set(duel.task_ids)) == 5
    assert not set(duel.task_ids) & quizzes["excluded"]

    opened = _client(bob).post(f"/api/social/duels/{duel.pk}/start/")
    assert opened.status_code == 200
    body = opened.json()
    assert [q["id"] for q in body["questions"]] == duel.task_ids
    assert "correct_answer" not in str(body) and "isCorrect" not in str(body)
    # a reload keeps the same clock, and both rivals see the options in the same (shuffled) order
    again = _client(bob).post(f"/api/social/duels/{duel.pk}/start/").json()
    assert again["deadline"] == body["deadline"]
    rival = _client(ann).post(f"/api/social/duels/{duel.pk}/start/").json()
    assert [q["options"] for q in rival["questions"]] == [q["options"] for q in body["questions"]]


def test_duel_is_scored_on_the_server_and_hides_the_rival_until_the_end(ann, bob, quizzes):
    _befriend(ann, bob)
    duel = services.create_duel(ann, bob)
    for user in (ann, bob):
        services.start_duel(user, duel.pk)

    mine = _client(ann).post(f"/api/social/duels/{duel.pk}/submit/", {"answers": _answers(duel, 4)}, format="json")
    assert mine.status_code == 200, mine.content
    assert mine.json()["me"]["correct"] == 4
    assert mine.json()["them"]["correct"] is None  # bob has not answered yet

    theirs = _client(bob).post(f"/api/social/duels/{duel.pk}/submit/", {"answers": _answers(duel, 2)}, format="json")
    assert theirs.json()["result"] == "loss"
    assert theirs.json()["them"]["correct"] == 4
    duel.refresh_from_db()
    assert duel.status == Duel.FINISHED and duel.winner == ann
    assert _client(ann).get("/api/social/duels/").json()["record"] == {"wins": 1, "draws": 0, "losses": 0}
    # a second answer is refused, and nothing in a duel pays XP or becomes a learning event
    again = _client(bob).post(f"/api/social/duels/{duel.pk}/submit/", {"answers": {}}, format="json")
    assert again.status_code == 409
    ann.profile.refresh_from_db()
    assert ann.profile.xp == 250
    assert not LearningEvent.objects.exists()


def test_late_answers_count_for_nothing(ann, bob, quizzes):
    _befriend(ann, bob)
    duel = services.create_duel(ann, bob)
    services.start_duel(ann, duel.pk)
    DuelAttempt.objects.filter(duel=duel, user=ann).update(
        started_at=timezone.now() - timedelta(seconds=services.DUEL_SECONDS + services.DUEL_GRACE_SECONDS + 5)
    )
    late = _client(ann).post(f"/api/social/duels/{duel.pk}/submit/", {"answers": _answers(duel, 5)}, format="json")
    assert late.status_code == 200
    assert late.json()["me"]["correct"] == 0 and late.json()["me"]["late"] is True


def test_decline_cancel_and_expiry(ann, bob, quizzes):
    _befriend(ann, bob)
    duel = services.create_duel(ann, bob)
    assert _client(ann).post("/api/social/duels/", {"username": "bob"}, format="json").json()["code"] == "already"
    assert _client(ann).post(f"/api/social/duels/{duel.pk}/decline/").status_code == 409  # only the opponent
    assert _client(bob).post(f"/api/social/duels/{duel.pk}/decline/").status_code == 200
    duel.refresh_from_db()
    assert duel.status == Duel.DECLINED

    second = services.create_duel(ann, bob)
    services.start_duel(bob, second.pk)
    assert _client(ann).post(f"/api/social/duels/{second.pk}/cancel/").status_code == 409  # bob already plays

    # nobody else answered before the deadline: whoever played wins
    services.submit_duel(bob, second.pk, _answers(second, 1))
    Duel.objects.filter(pk=second.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    listing = _client(ann).get("/api/social/duels/").json()
    row = next(item for item in listing["duels"] if item["id"] == second.pk)
    assert row["status"] == "finished" and row["result"] == "loss"


def test_duels_need_friends_and_enough_questions(ann, bob):
    assert _client(ann).post("/api/social/duels/", {"username": "bob"}, format="json").status_code == 403
    _befriend(ann, bob)
    no_questions = _client(ann).post("/api/social/duels/", {"username": "bob"}, format="json")
    assert no_questions.status_code == 409 and no_questions.json()["code"] == "no_questions"


def test_status_counts_what_waits_for_an_answer(ann, bob, quizzes):
    services.request_friend(bob, ann)
    services.request_friend(ann, bob)
    services.create_trade(bob, ann, "hint_scrolls", 1)
    services.create_duel(bob, ann)
    assert _client(ann).get("/api/social/status/").json() == {"friends": 0, "trades": 1, "duels": 1}
