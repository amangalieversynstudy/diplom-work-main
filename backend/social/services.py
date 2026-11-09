"""Rules of the tavern: friends, item exchange, guilds and quiz duels.

Shared rules:
* only players take part. A teacher or staff account (``can_teach``) is not a player, the same as on the
  leaderboard: in preview mode a teacher's items are free, so letting one hand them out would print items;
* nothing here pays XP, levels or achievements and nothing becomes a ``LearningEvent``;
* the whole layer can be switched off with ``SOCIAL_ENABLED=0``.
"""

import random
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status as http

from game.models import MissionTask, Progress
from game.services import public_task_data, quiz_answer_key, _norm
from users.models import Profile

from .models import GUILD_EMBLEMS, TRADE_ITEMS, Duel, DuelAttempt, Friendship, Guild, GuildMembership, ItemTrade

User = get_user_model()

MAX_FRIENDS = 100
MAX_PENDING_REQUESTS = 20
MAX_TRADE_QTY = 5
MAX_OPEN_TRADES = 5
MAX_TRADES_PER_DAY = 10
GUILD_MAX_MEMBERS = 20
GUILD_MIN_LEVEL = 2
DUEL_QUESTIONS = 5
DUEL_SECONDS = 120
DUEL_GRACE_SECONDS = 15
DUEL_DAYS = 3
MAX_OPEN_DUELS = 5
MAX_ANSWER_LENGTH = 200

TRADEABLE = tuple(key for key, _ in TRADE_ITEMS)
EMBLEMS = tuple(key for key, _ in GUILD_EMBLEMS)
GUILD_NAME_RE = re.compile(r"[\w\- '.!]+")


class SocialError(Exception):
    """A rule of the tavern was broken; the view turns it into ``{"detail", "code"}``."""

    def __init__(self, detail, code, status=http.HTTP_400_BAD_REQUEST):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status = status


# ── players ──────────────────────────────────────────────────────────────────


def is_player(user):
    return bool(
        user is not None
        and user.is_authenticated
        and user.is_active
        and not user.can_teach
        and not getattr(user, "email_verification_pending", False)
    )


def find_player(username):
    """The player with this login (any letter case), or None. Teachers and blocked accounts are not found."""
    username = (username or "").strip() if isinstance(username, str) else ""
    if not username or len(username) > 150:
        return None
    user = User.objects.filter(username__iexact=username).select_related("profile").first()
    return user if is_player(user) else None


def player_card(user):
    """What other players may see of a player: the same fields the public leaderboard shows."""
    profile = user.profile
    return {
        "id": user.pk,
        "username": user.username,
        "level": profile.level,
        "xp": profile.xp,
        "class_role_id": profile.class_role_id,
        "streak": profile.current_streak if profile.streak_active else 0,
    }


# ── friends ──────────────────────────────────────────────────────────────────


def _pair(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def friendship_between(a, b):
    low, high = _pair(a.pk, b.pk)
    return Friendship.objects.filter(user_low_id=low, user_high_id=high).first()


def are_friends(a, b):
    row = friendship_between(a, b)
    return row is not None and row.status == Friendship.ACCEPTED


def friend_ids(user):
    rows = Friendship.objects.filter(status=Friendship.ACCEPTED).filter(
        Q(user_low=user) | Q(user_high=user)
    ).values_list("user_low_id", "user_high_id")
    return {high if low == user.pk else low for low, high in rows}


def _accept(row):
    Friendship.objects.filter(pk=row.pk, status=Friendship.PENDING).update(
        status=Friendship.ACCEPTED, accepted_at=timezone.now()
    )


def _check_friend_room(*users):
    for user in users:
        if len(friend_ids(user)) >= MAX_FRIENDS:
            raise SocialError(
                f"У {user.username} уже {MAX_FRIENDS} друзей: это предел.", "friends_full", http.HTTP_409_CONFLICT
            )


def request_friend(user, target):
    """Send a friend request. If the other side has already asked, this answers yes. Returns the status."""
    if target.pk == user.pk:
        raise SocialError("Дружить с самим собой нельзя.", "self")
    row = friendship_between(user, target)
    if row is None:
        sent = Friendship.objects.filter(
            Q(user_low=user) | Q(user_high=user), status=Friendship.PENDING, requested_by=user
        ).count()
        if sent >= MAX_PENDING_REQUESTS:
            raise SocialError(
                "Слишком много заявок ждут ответа. Подожди, пока на них ответят.",
                "too_many_requests",
                http.HTTP_409_CONFLICT,
            )
        _check_friend_room(user, target)
        low, high = _pair(user.pk, target.pk)
        try:
            with transaction.atomic():
                Friendship.objects.create(user_low_id=low, user_high_id=high, requested_by=user)
            return Friendship.PENDING
        except IntegrityError:  # the other side asked at the same moment
            row = friendship_between(user, target)
            if row is None:
                raise
    if row.status == Friendship.ACCEPTED:
        return Friendship.ACCEPTED
    if row.requested_by_id == user.pk:
        return Friendship.PENDING
    _check_friend_room(user, target)
    _accept(row)
    return Friendship.ACCEPTED


def accept_friend(user, other):
    row = friendship_between(user, other)
    if row is None or row.status != Friendship.PENDING or row.requested_by_id == user.pk:
        raise SocialError("Заявки от этого игрока нет.", "no_request", http.HTTP_404_NOT_FOUND)
    _check_friend_room(user, other)
    _accept(row)


def remove_friend(user, other):
    """Unfriend, decline a request or take one's own request back. Open trade offers between them close."""
    row = friendship_between(user, other)
    if row is None:
        raise SocialError("Вы не друзья и заявок нет.", "not_found", http.HTTP_404_NOT_FOUND)
    with transaction.atomic():
        row.delete()
        ItemTrade.objects.filter(status=ItemTrade.PENDING).filter(
            Q(sender=user, receiver=other) | Q(sender=other, receiver=user)
        ).update(status=ItemTrade.CANCELLED, resolved_at=timezone.now())


def friends_overview(user):
    rows = Friendship.objects.filter(Q(user_low=user) | Q(user_high=user)).select_related(
        "user_low__profile", "user_high__profile"
    )
    friends, incoming, outgoing = [], [], []
    for row in rows:
        other = row.user_high if row.user_low_id == user.pk else row.user_low
        if not is_player(other):
            continue
        card = player_card(other)
        if row.status == Friendship.ACCEPTED:
            friends.append({**card, "since": row.accepted_at})
        elif row.requested_by_id == user.pk:
            outgoing.append({**card, "sent_at": row.created_at})
        else:
            incoming.append({**card, "sent_at": row.created_at})
    friends.sort(key=lambda card: (-card["xp"], card["username"].lower()))
    return {
        "friends": friends,
        "incoming": incoming,
        "outgoing": outgoing,
        "limits": {"friends": MAX_FRIENDS, "pending": MAX_PENDING_REQUESTS},
    }


# ── item exchange ────────────────────────────────────────────────────────────


def _quantity(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = None
    if number is None or isinstance(value, bool) or not low <= number <= high:
        raise SocialError(f"Количество — целое число от {low} до {high}.", "bad_quantity")
    return number


def create_trade(user, receiver, give_item, give_qty, ask_item=None, ask_qty=0):
    if give_item not in TRADEABLE or (ask_item and ask_item not in TRADEABLE):
        raise SocialError("Меняться можно только зельями ясности и свитками архитектора.", "bad_item")
    give_qty = _quantity(give_qty, 1, MAX_TRADE_QTY)
    ask_qty = _quantity(ask_qty or 0, 0, MAX_TRADE_QTY)
    if ask_qty and not ask_item:
        raise SocialError("Укажи, какой предмет просишь взамен.", "bad_item")
    if not ask_qty:
        ask_item = ""
    if receiver.pk == user.pk:
        raise SocialError("Меняться с самим собой нельзя.", "self")
    if not are_friends(user, receiver):
        raise SocialError("Меняться можно только с друзьями.", "not_friends", http.HTTP_403_FORBIDDEN)
    if getattr(user.profile, give_item) < give_qty:
        raise SocialError("Столько предметов у тебя нет.", "not_enough", http.HTTP_409_CONFLICT)
    if ItemTrade.objects.filter(sender=user, status=ItemTrade.PENDING).count() >= MAX_OPEN_TRADES:
        raise SocialError(
            f"Открыто уже {MAX_OPEN_TRADES} предложений. Дождись ответа или отзови одно.",
            "too_many_trades",
            http.HTTP_409_CONFLICT,
        )
    return ItemTrade.objects.create(
        sender=user, receiver=receiver, give_item=give_item, give_qty=give_qty, ask_item=ask_item, ask_qty=ask_qty
    )


def _trades_today(user):
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return ItemTrade.objects.filter(
        Q(sender=user) | Q(receiver=user), status=ItemTrade.ACCEPTED, resolved_at__gte=start
    ).count()


def _take(user_id, item, qty, detail, code):
    """Take *qty* of *item* from a profile in one conditional UPDATE, or fail (and roll the whole trade back)."""
    taken = Profile.objects.filter(user_id=user_id, **{f"{item}__gte": qty}).update(**{item: F(item) - qty})
    if not taken:
        raise SocialError(detail, code, http.HTTP_409_CONFLICT)


def _give(user_id, item, qty):
    Profile.objects.filter(user_id=user_id).update(**{item: F(item) + qty})


def accept_trade(user, trade_id):
    """Swap the items. Everything happens in one transaction: a failed step leaves both inventories as they were."""
    with transaction.atomic():
        trade = (
            ItemTrade.objects.select_for_update()
            .select_related("sender")
            .filter(pk=trade_id, receiver=user)
            .first()
        )
        if trade is None:
            raise SocialError("Предложение не найдено.", "not_found", http.HTTP_404_NOT_FOUND)
        if trade.status != ItemTrade.PENDING:
            raise SocialError("Это предложение уже закрыто.", "closed", http.HTTP_409_CONFLICT)
        if not is_player(trade.sender) or not are_friends(trade.sender, user):
            raise SocialError("Меняться можно только с друзьями.", "not_friends", http.HTTP_403_FORBIDDEN)
        if _trades_today(user) >= MAX_TRADES_PER_DAY or _trades_today(trade.sender) >= MAX_TRADES_PER_DAY:
            raise SocialError(
                f"Не больше {MAX_TRADES_PER_DAY} обменов в день. Продолжим завтра.",
                "daily_limit",
                http.HTTP_429_TOO_MANY_REQUESTS,
            )
        _take(trade.sender_id, trade.give_item, trade.give_qty, "У друга уже нет этих предметов.", "sender_short")
        if trade.ask_qty:
            _take(user.pk, trade.ask_item, trade.ask_qty, "У тебя нет предметов, которые просят взамен.", "receiver_short")
            _give(trade.sender_id, trade.ask_item, trade.ask_qty)
        _give(user.pk, trade.give_item, trade.give_qty)
        trade.status = ItemTrade.ACCEPTED
        trade.resolved_at = timezone.now()
        trade.save(update_fields=["status", "resolved_at"])
    return trade


def close_trade(user, trade_id, action):
    """The receiver declines, or the sender takes the offer back."""
    field, new_status = ("receiver", ItemTrade.DECLINED) if action == "decline" else ("sender", ItemTrade.CANCELLED)
    closed = ItemTrade.objects.filter(pk=trade_id, status=ItemTrade.PENDING, **{field: user}).update(
        status=new_status, resolved_at=timezone.now()
    )
    if not closed:
        raise SocialError("Открытого предложения нет.", "not_found", http.HTTP_404_NOT_FOUND)


def _trade_payload(trade, user):
    other = trade.receiver if trade.sender_id == user.pk else trade.sender
    return {
        "id": trade.pk,
        "direction": "out" if trade.sender_id == user.pk else "in",
        "other": {"id": other.pk, "username": other.username},
        "give_item": trade.give_item,
        "give_qty": trade.give_qty,
        "ask_item": trade.ask_item or None,
        "ask_qty": trade.ask_qty,
        "status": trade.status,
        "created_at": trade.created_at,
        "resolved_at": trade.resolved_at,
    }


def trades_overview(user):
    mine = ItemTrade.objects.filter(Q(sender=user) | Q(receiver=user)).select_related("sender", "receiver")
    pending = [_trade_payload(t, user) for t in mine.filter(status=ItemTrade.PENDING)]
    history = [_trade_payload(t, user) for t in mine.exclude(status=ItemTrade.PENDING)[:20]]
    profile = user.profile
    return {
        "incoming": [t for t in pending if t["direction"] == "in"],
        "outgoing": [t for t in pending if t["direction"] == "out"],
        "history": history,
        "inventory": {item: getattr(profile, item) for item in TRADEABLE},
        "limits": {"qty": MAX_TRADE_QTY, "open": MAX_OPEN_TRADES, "per_day": MAX_TRADES_PER_DAY},
    }


# ── guilds ───────────────────────────────────────────────────────────────────


def clean_guild_name(name):
    name = " ".join(name.split()) if isinstance(name, str) else ""
    if not 3 <= len(name) <= 40:
        raise SocialError("Название гильдии — от 3 до 40 символов.", "bad_name")
    if not GUILD_NAME_RE.fullmatch(name):
        raise SocialError("В названии можно буквы, цифры, пробел и знаки - ' . !", "bad_name")
    return name


def guild_rows():
    """Guilds with their member count and the sum of their players' XP, best first."""
    players = Q(memberships__user__is_teacher=False, memberships__user__is_staff=False)
    return (
        Guild.objects.annotate(
            members=Count("memberships", distinct=True),
            total_xp=Coalesce(Sum("memberships__user__profile__xp", filter=players), Value(0), output_field=IntegerField()),
        )
        .select_related("leader")
        .order_by("-total_xp", "-members", "name")
    )


def _guild_payload(guild, place=None):
    return {
        "id": guild.pk,
        "name": guild.name,
        "motto": guild.motto,
        "emblem": guild.emblem,
        "leader": guild.leader.username if guild.leader_id else None,
        "members": getattr(guild, "members", None),
        "total_xp": getattr(guild, "total_xp", None),
        "place": place,
        "created_at": guild.created_at,
    }


def guilds_overview(user):
    rows = list(guild_rows()[:100])
    membership = GuildMembership.objects.filter(user=user).first()
    return {
        "guilds": [_guild_payload(guild, place) for place, guild in enumerate(rows, start=1)],
        "mine": membership.guild_id if membership else None,
        "limits": {"members": GUILD_MAX_MEMBERS, "min_level": GUILD_MIN_LEVEL},
        "emblems": list(EMBLEMS),
    }


def guild_detail(guild_id, user):
    guild = guild_rows().filter(pk=guild_id).first()
    if guild is None:
        raise SocialError("Гильдия не найдена.", "not_found", http.HTTP_404_NOT_FOUND)
    members = guild.memberships.select_related("user__profile").order_by("joined_at", "id")
    payload = _guild_payload(guild)
    payload["members_list"] = [
        {**player_card(m.user), "joined_at": m.joined_at, "is_leader": m.user_id == guild.leader_id}
        for m in members
    ]
    payload["is_member"] = any(m.user_id == user.pk for m in members)
    payload["is_leader"] = guild.leader_id == user.pk
    payload["max_members"] = GUILD_MAX_MEMBERS
    return payload


def create_guild(user, name, motto="", emblem="dragon"):
    if user.profile.level < GUILD_MIN_LEVEL:
        raise SocialError(
            f"Основать гильдию может герой {GUILD_MIN_LEVEL}-го уровня и выше.", "low_level", http.HTTP_403_FORBIDDEN
        )
    if GuildMembership.objects.filter(user=user).exists():
        raise SocialError("Ты уже состоишь в гильдии.", "in_guild", http.HTTP_409_CONFLICT)
    name = clean_guild_name(name)
    motto = " ".join(motto.split())[:120] if isinstance(motto, str) else ""
    emblem = emblem if emblem in EMBLEMS else EMBLEMS[0]
    if Guild.objects.filter(name_key=name.casefold()).exists():
        raise SocialError("Такое название уже занято.", "name_taken", http.HTTP_409_CONFLICT)
    try:
        with transaction.atomic():
            guild = Guild.objects.create(name=name, motto=motto, emblem=emblem, leader=user)
            GuildMembership.objects.create(user=user, guild=guild)
    except IntegrityError:
        if Guild.objects.filter(name_key=name.casefold()).exists():
            raise SocialError("Такое название уже занято.", "name_taken", http.HTTP_409_CONFLICT)
        raise SocialError("Ты уже состоишь в гильдии.", "in_guild", http.HTTP_409_CONFLICT)
    return guild


def join_guild(user, guild_id):
    with transaction.atomic():
        # the guild row is locked, so two players cannot both take the last free place
        guild = Guild.objects.select_for_update().filter(pk=guild_id).first()
        if guild is None:
            raise SocialError("Гильдия не найдена.", "not_found", http.HTTP_404_NOT_FOUND)
        if GuildMembership.objects.filter(user=user).exists():
            raise SocialError("Ты уже состоишь в гильдии. Сначала выйди из неё.", "in_guild", http.HTTP_409_CONFLICT)
        if guild.memberships.count() >= GUILD_MAX_MEMBERS:
            raise SocialError("В гильдии нет мест.", "guild_full", http.HTTP_409_CONFLICT)
        try:
            with transaction.atomic():
                GuildMembership.objects.create(user=user, guild=guild)
        except IntegrityError:
            raise SocialError("Ты уже состоишь в гильдии.", "in_guild", http.HTTP_409_CONFLICT)
    return guild


def leave_guild(user):
    """Leave; a leaving leader hands the guild to the oldest member, and an empty guild is dissolved."""
    with transaction.atomic():
        membership = GuildMembership.objects.filter(user=user).first()
        if membership is None:
            raise SocialError("Ты не состоишь в гильдии.", "not_in_guild", http.HTTP_404_NOT_FOUND)
        guild = Guild.objects.select_for_update().get(pk=membership.guild_id)
        membership.delete()
        heir = guild.memberships.select_related("user").order_by("joined_at", "id").first()
        if heir is None:
            guild.delete()
            return None
        if guild.leader_id in (None, user.pk):
            guild.leader = heir.user
            guild.save(update_fields=["leader"])
    return guild


def kick_member(leader, guild_id, user_id):
    guild = Guild.objects.filter(pk=guild_id, leader=leader).first()
    if guild is None:
        raise SocialError("Исключать может только глава гильдии.", "not_leader", http.HTTP_403_FORBIDDEN)
    if user_id == leader.pk:
        raise SocialError("Глава не исключает сам себя: можно выйти из гильдии.", "self")
    removed, _ = GuildMembership.objects.filter(guild=guild, user_id=user_id).delete()
    if not removed:
        raise SocialError("Такого участника нет.", "not_found", http.HTTP_404_NOT_FOUND)


# ── duels ────────────────────────────────────────────────────────────────────


def usable_question(task):
    """A plain multiple-choice quiz with a key. An "explain" step talks about the learner's own code and a
    step with variants has numbers of its own for everyone, so neither can be one shared question."""
    data = task.data if isinstance(task.data, dict) else {}
    if task.kind == "explain" or data.get("variants"):
        return False
    options = data.get("options")
    return isinstance(options, list) and len(options) >= 2 and quiz_answer_key(task) is not None


def question_pool():
    """Quiz steps of published missions in public, published courses, in course order."""
    tasks = (
        MissionTask.objects.filter(
            task_type="quiz",
            mission__is_active=True,
            mission__location__track__is_active=True,
            mission__location__track__is_public=True,
        )
        .select_related("mission__location__track")
        .order_by("mission__location__track__order", "mission__location__order", "mission__order", "order", "id")
    )
    return [task for task in tasks if usable_question(task)]


def _completed_missions(user):
    return set(Progress.objects.filter(user=user, completed=True).values_list("mission_id", flat=True))


def pick_questions(a, b, rng=None):
    """Five questions: first from missions both players finished, then from what either finished, then
    from the start of the course (questions on untouched topics come from its easiest part)."""
    rng = rng or random.SystemRandom()
    pool = question_pool()
    if len(pool) < DUEL_QUESTIONS:
        raise SocialError("Для дуэли пока мало вопросов в курсах.", "no_questions", http.HTTP_409_CONFLICT)
    done_a, done_b = _completed_missions(a), _completed_missions(b)
    both = [t for t in pool if t.mission_id in done_a and t.mission_id in done_b]
    either = [t for t in pool if (t.mission_id in done_a) != (t.mission_id in done_b)]
    rest = [t for t in pool if t.mission_id not in done_a and t.mission_id not in done_b]
    picked = []
    for group in (both, either, rest[: max(15, DUEL_QUESTIONS)], rest[max(15, DUEL_QUESTIONS):]):
        need = DUEL_QUESTIONS - len(picked)
        if need <= 0:
            break
        picked.extend(rng.sample(group, min(need, len(group))))
    return [task.pk for task in picked]


def _open_duels(user):
    return Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status=Duel.ACTIVE)


def create_duel(user, opponent):
    if opponent.pk == user.pk:
        raise SocialError("Вызвать на дуэль самого себя нельзя.", "self")
    if not are_friends(user, opponent):
        raise SocialError("Вызвать на дуэль можно только друга.", "not_friends", http.HTTP_403_FORBIDDEN)
    if _open_duels(user).filter(Q(challenger=opponent) | Q(opponent=opponent)).exists():
        raise SocialError("С этим другом дуэль уже идёт.", "already", http.HTTP_409_CONFLICT)
    if _open_duels(user).count() >= MAX_OPEN_DUELS:
        raise SocialError(
            f"Одновременно можно вести не больше {MAX_OPEN_DUELS} дуэлей.", "too_many_duels", http.HTTP_409_CONFLICT
        )
    task_ids = pick_questions(user, opponent)
    return Duel.objects.create(
        challenger=user,
        opponent=opponent,
        task_ids=task_ids,
        expires_at=timezone.now() + timedelta(days=DUEL_DAYS),
    )


def _duration(attempt):
    return (attempt.submitted_at - attempt.started_at).total_seconds()


def _finish_if_done(duel, now=None):
    """Both sides answered: the one with more right answers wins; with a tie the faster one (by a second or
    more, timed on the server), otherwise a draw."""
    done = [a for a in duel.attempts.all() if a.submitted_at]
    if len(done) < 2:
        return
    first, second = done
    winner = None
    if first.correct != second.correct:
        winner = first if first.correct > second.correct else second
    elif abs(_duration(first) - _duration(second)) >= 1:
        winner = first if _duration(first) < _duration(second) else second
    duel.status = Duel.FINISHED
    duel.finished_at = now or timezone.now()
    duel.winner_id = winner.user_id if winner else None
    duel.save(update_fields=["status", "finished_at", "winner"])


def refresh_duel(duel, now=None):
    """Close what time has closed: an attempt past its limit counts as answered with nothing right, and a
    duel past ``expires_at`` goes to whoever played (or expires if nobody did)."""
    if duel.status != Duel.ACTIVE:
        return duel
    now = now or timezone.now()
    limit = timedelta(seconds=DUEL_SECONDS + DUEL_GRACE_SECONDS)
    for attempt in duel.attempts.all():
        if attempt.submitted_at is None and now > attempt.started_at + limit:
            attempt.submitted_at = attempt.started_at + limit
            attempt.correct = 0
            attempt.late = True
            attempt.save(update_fields=["submitted_at", "correct", "late"])
    _finish_if_done(duel, now)
    if duel.status == Duel.ACTIVE and now >= duel.expires_at:
        done = [a for a in duel.attempts.all() if a.submitted_at]
        duel.status = Duel.FINISHED if done else Duel.EXPIRED
        duel.finished_at = now
        duel.winner_id = done[0].user_id if done else None
        duel.save(update_fields=["status", "finished_at", "winner"])
    return duel


def _my_duel(user, duel_id, lock=False):
    qs = Duel.objects.filter(pk=duel_id).filter(Q(challenger=user) | Q(opponent=user))
    if lock:
        qs = qs.select_for_update()
    duel = qs.select_related("challenger__profile", "opponent__profile").first()
    if duel is None:
        raise SocialError("Дуэль не найдена.", "not_found", http.HTTP_404_NOT_FOUND)
    return duel


def _question(task, lang, duel_id):
    # The course keeps the right option first in many quizzes; in a duel "always take the first one" must not
    # win. The order is shuffled with a seed of the duel and the step, so both rivals see the same order.
    options = list(public_task_data(task).get("options", []))
    random.Random(f"{duel_id}:{task.pk}").shuffle(options)
    return {
        "id": task.pk,
        "title": task.get_localized_title(lang),
        "body": task.get_localized_body(lang),
        "options": options,
    }


def start_duel(user, duel_id, lang="ru"):
    """Open the questions. The clock starts on the first call; a reload gets the same questions and deadline."""
    duel = refresh_duel(_my_duel(user, duel_id))
    if duel.status != Duel.ACTIVE:
        raise SocialError("Эта дуэль уже закончилась.", "closed", http.HTTP_409_CONFLICT)
    attempt, _ = DuelAttempt.objects.get_or_create(duel=duel, user=user, defaults={"started_at": timezone.now()})
    if attempt.submitted_at:
        raise SocialError("Ты уже ответил в этой дуэли.", "already_submitted", http.HTTP_409_CONFLICT)
    tasks = MissionTask.objects.in_bulk(duel.task_ids)
    return {
        "duel": duel_payload(duel, user),
        "questions": [_question(tasks[pk], lang, duel.pk) for pk in duel.task_ids if pk in tasks],
        "deadline": attempt.started_at + timedelta(seconds=DUEL_SECONDS),
        "seconds": DUEL_SECONDS,
        "server_now": timezone.now(),
    }


def _graded(task, given):
    if task is None or given is None or isinstance(given, (dict, list)):
        return False
    given = str(given)
    if len(given) > MAX_ANSWER_LENGTH:
        return False
    key = quiz_answer_key(task)
    return key is not None and _norm(given) == key


def submit_duel(user, duel_id, answers):
    """Check the answers on the server. Late answers (past the limit and a short grace) count for nothing."""
    with transaction.atomic():
        duel = _my_duel(user, duel_id, lock=True)
        attempt = DuelAttempt.objects.select_for_update().filter(duel=duel, user=user).first()
        if attempt is None:
            raise SocialError("Сначала открой вопросы дуэли.", "not_started", http.HTTP_409_CONFLICT)
        if attempt.submitted_at:
            raise SocialError("Ты уже ответил в этой дуэли.", "already_submitted", http.HTTP_409_CONFLICT)
        if duel.status != Duel.ACTIVE:
            raise SocialError("Эта дуэль уже закончилась.", "closed", http.HTTP_409_CONFLICT)
        now = timezone.now()
        late = now > attempt.started_at + timedelta(seconds=DUEL_SECONDS + DUEL_GRACE_SECONDS)
        answers = answers if isinstance(answers, dict) else {}
        tasks = MissionTask.objects.in_bulk(duel.task_ids)
        results = {str(pk): (not late) and _graded(tasks.get(pk), answers.get(str(pk))) for pk in duel.task_ids}
        attempt.submitted_at = now
        attempt.correct = sum(results.values())
        attempt.results = results
        attempt.late = late
        attempt.save(update_fields=["submitted_at", "correct", "results", "late"])
        _finish_if_done(duel, now)
    return duel_payload(duel, user)


def close_duel(user, duel_id, action):
    """The opponent declines before playing, or the challenger withdraws before the opponent has played."""
    with transaction.atomic():
        duel = _my_duel(user, duel_id, lock=True)
        if duel.status != Duel.ACTIVE:
            raise SocialError("Эта дуэль уже закончилась.", "closed", http.HTTP_409_CONFLICT)
        if action == "decline":
            if duel.opponent_id != user.pk or duel.attempts.filter(user=user).exists():
                raise SocialError("Отказаться можно от вызова, который ещё не начат.", "cannot", http.HTTP_409_CONFLICT)
            duel.status = Duel.DECLINED
        else:
            if duel.challenger_id != user.pk or duel.attempts.filter(user_id=duel.opponent_id).exists():
                raise SocialError("Отозвать можно вызов, который соперник ещё не начал.", "cannot", http.HTTP_409_CONFLICT)
            duel.status = Duel.CANCELLED
        duel.finished_at = timezone.now()
        duel.save(update_fields=["status", "finished_at"])
    return duel_payload(duel, user)


def _side(attempt, reveal):
    if attempt is None:
        return {"started": False, "submitted": False, "correct": None, "late": False}
    submitted = attempt.submitted_at is not None
    return {
        "started": True,
        "submitted": submitted,
        "correct": attempt.correct if submitted and reveal else None,
        "late": attempt.late if submitted and reveal else False,
    }


def duel_payload(duel, user):
    attempts = {a.user_id: a for a in duel.attempts.all()}
    mine = attempts.get(user.pk)
    other = duel.opponent if duel.challenger_id == user.pk else duel.challenger
    theirs = attempts.get(other.pk)
    finished = duel.status == Duel.FINISHED
    result = None
    if finished:
        result = "draw" if duel.winner_id is None else ("win" if duel.winner_id == user.pk else "loss")
    active = duel.status == Duel.ACTIVE
    role = "challenger" if duel.challenger_id == user.pk else "opponent"
    return {
        "id": duel.pk,
        "status": duel.status,
        "role": role,
        "opponent": {"id": other.pk, "username": other.username, "level": other.profile.level},
        "questions": len(duel.task_ids),
        "seconds": DUEL_SECONDS,
        "created_at": duel.created_at,
        "expires_at": duel.expires_at,
        "finished_at": duel.finished_at,
        # your own score shows once you answered; the rival's only when the duel is over
        "me": _side(mine, reveal=True),
        "them": _side(theirs, reveal=finished),
        "result": result,
        "can_start": active and (mine is None or mine.submitted_at is None),
        "can_decline": active and role == "opponent" and mine is None,
        "can_cancel": active and role == "challenger" and theirs is None,
    }


def duels_overview(user):
    duels = list(
        Duel.objects.filter(Q(challenger=user) | Q(opponent=user))
        .select_related("challenger__profile", "opponent__profile")
        .prefetch_related("attempts")
        .order_by("-created_at")[:30]
    )
    now = timezone.now()
    for duel in duels:
        refresh_duel(duel, now)
    finished = Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status=Duel.FINISHED)
    record = finished.aggregate(
        wins=Count("pk", filter=Q(winner=user)),
        draws=Count("pk", filter=Q(winner__isnull=True)),
        total=Count("pk"),
    )
    return {
        "duels": [duel_payload(duel, user) for duel in duels],
        "record": {
            "wins": record["wins"],
            "draws": record["draws"],
            "losses": record["total"] - record["wins"] - record["draws"],
        },
        "limits": {"questions": DUEL_QUESTIONS, "seconds": DUEL_SECONDS, "days": DUEL_DAYS, "open": MAX_OPEN_DUELS},
    }


def tavern_status(user):
    """Counters for the tavern's tabs: what waits for this player's answer."""
    incoming_friends = Friendship.objects.filter(
        Q(user_low=user) | Q(user_high=user), status=Friendship.PENDING
    ).exclude(requested_by=user).count()
    incoming_trades = ItemTrade.objects.filter(receiver=user, status=ItemTrade.PENDING).count()
    duels = _open_duels(user).filter(expires_at__gt=timezone.now()).exclude(attempts__user=user).count()
    return {"friends": incoming_friends, "trades": incoming_trades, "duels": duels}
