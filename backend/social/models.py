"""The tavern: the social layer of the game.

Friends, an exchange of inventory items between friends, guilds and quiz duels. Nothing here pays XP,
levels or achievements, and nothing is written to ``game.LearningEvent``: the research data (activity,
help items, performance) and the leaderboard stay exactly what they were before the tavern existed.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Friendship(models.Model):
    """One row per pair of players, whoever asked first. ``user_low`` is always the smaller id."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    STATUS_CHOICES = ((PENDING, "ждёт ответа"), (ACCEPTED, "друзья"))

    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="игрок A", on_delete=models.CASCADE, related_name="+"
    )
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="игрок B", on_delete=models.CASCADE, related_name="+"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="кто предложил", on_delete=models.CASCADE, related_name="+"
    )
    status = models.CharField("статус", max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField("заявка", auto_now_add=True)
    accepted_at = models.DateTimeField("дружба с", null=True, blank=True)

    class Meta:
        verbose_name = "дружба"
        verbose_name_plural = "дружба"
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="one_friendship_per_pair"),
            models.CheckConstraint(condition=Q(user_low__lt=F("user_high")), name="friendship_pair_ordered"),
        ]

    def __str__(self):
        return f"{self.user_low_id} & {self.user_high_id} ({self.status})"


TRADE_ITEMS = (
    ("hint_scrolls", "Зелье ясности"),
    ("skeleton_scrolls", "Свиток архитектора"),
)


class ItemTrade(models.Model):
    """An offer of items to a friend. ``ask_qty`` = 0 makes it a gift.

    Items move only when the friend accepts, in one transaction with conditional updates, so nobody can
    give away what they no longer have. The AI mentor's calls are not tradeable: they spend a paid API quota.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (PENDING, "ждёт ответа"),
        (ACCEPTED, "принято"),
        (DECLINED, "отклонено"),
        (CANCELLED, "отозвано"),
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="кто предлагает", on_delete=models.CASCADE, related_name="trades_sent"
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="кому", on_delete=models.CASCADE, related_name="trades_received"
    )
    give_item = models.CharField("отдаёт", max_length=20, choices=TRADE_ITEMS)
    give_qty = models.PositiveSmallIntegerField("сколько отдаёт")
    ask_item = models.CharField("просит", max_length=20, choices=TRADE_ITEMS, blank=True)
    ask_qty = models.PositiveSmallIntegerField("сколько просит", default=0)
    status = models.CharField("статус", max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField("создано", auto_now_add=True)
    resolved_at = models.DateTimeField("закрыто", null=True, blank=True)

    class Meta:
        verbose_name = "обмен предметами"
        verbose_name_plural = "обмены предметами"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(sender=F("receiver")), name="trade_not_with_self"),
            models.CheckConstraint(condition=Q(give_qty__gte=1, give_qty__lte=5), name="trade_give_1_to_5"),
            models.CheckConstraint(condition=Q(ask_qty__gte=0, ask_qty__lte=5), name="trade_ask_0_to_5"),
        ]
        indexes = [models.Index(fields=["receiver", "status"]), models.Index(fields=["sender", "status"])]

    def __str__(self):
        return f"{self.sender_id} -> {self.receiver_id}: {self.give_qty} {self.give_item} ({self.status})"


GUILD_EMBLEMS = (
    ("dragon", "Дракон"),
    ("owl", "Сова"),
    ("wolf", "Волк"),
    ("phoenix", "Феникс"),
    ("tower", "Башня"),
    ("serpent", "Змей"),
)


class Guild(models.Model):
    """A band of players. Its standing is the sum of its members' platform XP."""

    name = models.CharField("название", max_length=40)
    # the name in one letter case (str.casefold): unique, so «Совы» and «СОВЫ» cannot both exist on any
    # database (SQLite's lower() folds only ASCII letters)
    name_key = models.CharField("ключ названия", max_length=40, unique=True, editable=False)
    motto = models.CharField("девиз", max_length=120, blank=True)
    emblem = models.CharField("герб", max_length=16, choices=GUILD_EMBLEMS, default="dragon")
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="глава",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_guilds",
    )
    created_at = models.DateTimeField("основана", auto_now_add=True)

    class Meta:
        verbose_name = "гильдия"
        verbose_name_plural = "гильдии"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name_key = self.name.casefold()
        if kwargs.get("update_fields") is not None and "name" in kwargs["update_fields"]:
            kwargs["update_fields"] = {*kwargs["update_fields"], "name_key"}
        super().save(*args, **kwargs)


class GuildMembership(models.Model):
    """A player belongs to at most one guild."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="игрок", on_delete=models.CASCADE, related_name="guild_membership"
    )
    guild = models.ForeignKey(Guild, verbose_name="гильдия", on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField("вступил", auto_now_add=True)

    class Meta:
        verbose_name = "участник гильдии"
        verbose_name_plural = "участники гильдий"
        ordering = ["joined_at", "id"]

    def __str__(self):
        return f"{self.user_id} in {self.guild_id}"


class Duel(models.Model):
    """A quiz duel between two friends: the same questions, a time limit, answers checked on the server.

    Both sides play whenever they like within ``expires_at``; the duel ends when both have answered.
    """

    ACTIVE = "active"
    FINISHED = "finished"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = (
        (ACTIVE, "идёт"),
        (FINISHED, "завершена"),
        (DECLINED, "отклонена"),
        (CANCELLED, "отозвана"),
        (EXPIRED, "никто не сыграл"),
    )

    challenger = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="вызвал", on_delete=models.CASCADE, related_name="duels_started"
    )
    opponent = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="соперник", on_delete=models.CASCADE, related_name="duels_received"
    )
    task_ids = models.JSONField("вопросы (id шагов-квизов)", default=list)
    status = models.CharField("статус", max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="победитель",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duels_won",
    )
    created_at = models.DateTimeField("вызов", auto_now_add=True)
    expires_at = models.DateTimeField("сыграть до")
    finished_at = models.DateTimeField("итог", null=True, blank=True)

    class Meta:
        verbose_name = "дуэль"
        verbose_name_plural = "дуэли"
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=~Q(challenger=F("opponent")), name="duel_not_with_self")]

    def __str__(self):
        return f"{self.challenger_id} vs {self.opponent_id} ({self.status})"


class DuelAttempt(models.Model):
    """One side of a duel: when the questions were opened, when answered and how many were right."""

    duel = models.ForeignKey(Duel, verbose_name="дуэль", on_delete=models.CASCADE, related_name="attempts")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="игрок", on_delete=models.CASCADE, related_name="duel_attempts"
    )
    started_at = models.DateTimeField("открыл вопросы")
    submitted_at = models.DateTimeField("ответил", null=True, blank=True)
    correct = models.PositiveSmallIntegerField("верных ответов", default=0)
    results = models.JSONField("верно ли по вопросам", default=dict, blank=True)
    late = models.BooleanField("не успел", default=False)

    class Meta:
        verbose_name = "попытка в дуэли"
        verbose_name_plural = "попытки в дуэлях"
        constraints = [models.UniqueConstraint(fields=["duel", "user"], name="one_attempt_per_duel_side")]

    def __str__(self):
        return f"{self.user_id} in duel {self.duel_id}: {self.correct}"
