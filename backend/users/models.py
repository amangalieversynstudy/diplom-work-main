"""Custom user model and profile management."""

from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import uuid


class User(AbstractUser):
    """Custom user model with optional display name."""

    display_name = models.CharField(max_length=150, blank=True)


class Profile(models.Model):
    """Profile stores game-related user state such as XP, level, and inventory."""

    user = models.OneToOneField(
        "users.User", on_delete=models.CASCADE, related_name="profile"
    )
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    bio = models.TextField(blank=True)
    
    # Optional selected hero class/role
    class_role = models.ForeignKey(
        "game.ClassRole",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
    )

    # --- ИНВЕНТАРЬ (Inventory) ---
    ai_summons = models.PositiveIntegerField(
        default=3, 
        help_text="Количество вызовов AI-помощника (AI Summon Item)"
    )
    hint_scrolls = models.PositiveIntegerField(
        default=5, 
        help_text="Зелья ясности (Hint Scroll - подсветка синтаксиса/ошибок)"
    )
    skeleton_scrolls = models.PositiveIntegerField(
        default=3,
        help_text="Свитки Архитектора (Skeleton Scroll - вставка стартового кода)"
    )
    # Серия завершений подряд (Streak). Используется как secondary
    # tiebreaker в лидерборде после xp_total. Обновляется методом
    # register_activity() при каждом Progress.complete(): растёт на
    # подряд идущих днях и сбрасывается, если день пропущен.
    current_streak = models.PositiveIntegerField(
        default=0,
        help_text="Текущая серия дней с завершённой миссией"
    )
    longest_streak = models.PositiveIntegerField(
        default=0,
        help_text="Лучшая серия за всё время"
    )
    # Дата последнего дня, который был засчитан в стрик. Нужна, чтобы
    # отличить «уже отметился сегодня» от «новый день» и понять, жива ли
    # серия (последняя активность сегодня/вчера) или уже оборвана.
    last_streak_date = models.DateField(
        null=True,
        blank=True,
        help_text="Дата последнего засчитанного в стрик дня"
    )
    # Дата последнего отправленного email-напоминания о стрике. Нужна, чтобы
    # команда send_streak_reminders не слала повторное письмо в тот же день.
    last_streak_reminder = models.DateField(
        null=True,
        blank=True,
        help_text="Дата последнего email-напоминания о стрике"
    )

    def use_item(self, item_field_name: str) -> bool:
        """
        Пытается списать 1 предмет из инвентаря.
        Возвращает True в случае успеха, False если предмета нет в наличии или поле не найдено.
        """
        # Проверяем, что запрашиваемое поле действительно относится к инвентарю
        allowed_items = ["ai_summons", "hint_scrolls", "skeleton_scrolls"]
        
        if item_field_name in allowed_items and hasattr(self, item_field_name):
            current_amount = getattr(self, item_field_name)
            if current_amount > 0:
                setattr(self, item_field_name, current_amount - 1)
                # update_fields оптимизирует запрос к БД, обновляя только одно поле
                self.save(update_fields=[item_field_name])
                return True
        return False

    def add_xp(self, amount):
        """Add XP to the profile and adjust level when thresholds are crossed.

        Если уровень повысился — пополняем инвентарь как награду за level-up
        (см. MID-07). Возвращает кортеж (leveled_up, old_level, new_level).
        """
        old_level = self.level
        self.xp += amount
        # simple leveling rule: every 100 XP = level up
        new_level = self.xp // 100 + 1
        leveled_up = new_level > old_level
        if leveled_up:
            self.level = new_level
            # Награда за каждый новый уровень: +1 hint, +1 ai_summon
            levels_gained = new_level - old_level
            self.hint_scrolls += levels_gained
            self.ai_summons += levels_gained
        self.save()
        return leveled_up, old_level, new_level

    def register_activity(self, today=None):
        """Засчитать активность игрока в дневной стрик.

        Вызывается ровно при завершении миссии (``Progress.complete``).
        Логика по дням: первый засчитанный день за сегодня продлевает серию,
        если вчера тоже был засчитан, иначе серия начинается заново с 1.
        Повторные завершения в тот же день не считаются. ``today`` можно
        передать явно (для тестов); по умолчанию берётся локальная дата.

        Возвращает True, если счётчик изменился (засчитан новый день).
        """
        today = today or timezone.localdate()
        last = self.last_streak_date
        if last == today:
            return False  # уже отметились сегодня — без двойного счёта
        if last == today - timedelta(days=1):
            self.current_streak = (self.current_streak or 0) + 1
        else:
            self.current_streak = 1  # первый день или серия прервалась
        if self.current_streak > (self.longest_streak or 0):
            self.longest_streak = self.current_streak
        self.last_streak_date = today
        self.save(
            update_fields=["current_streak", "longest_streak", "last_streak_date"]
        )
        return True

    @property
    def streak_active(self):
        """Жива ли серия: последний засчитанный день — сегодня или вчера.

        Если активности не было больше суток, серия считается оборванной
        (следующее завершение начнёт её заново), поэтому показываем 0.
        """
        if not self.last_streak_date or not self.current_streak:
            return False
        return self.last_streak_date >= timezone.localdate() - timedelta(days=1)

    @property
    def streak_at_risk(self):
        """Серия жива, но сегодня ещё не продлена — повод напомнить игроку
        («заверши миссию сегодня, чтобы не потерять серию»)."""
        return self.streak_active and self.last_streak_date != timezone.localdate()

    @property
    def current_rank(self):
        """Find the highest Rank the player qualifies for based on level/xp.

        Lazy-import to avoid circular dependency (game.Rank depends on
        users via FK chain). Returns dict or None if no ranks configured.
        """
        from game.models import Rank
        rank = (
            Rank.objects
            .filter(min_level__lte=self.level, min_xp__lte=self.xp)
            .order_by("-min_level", "-min_xp")
            .first()
        )
        if not rank:
            return None
        return {
            "slug": rank.slug,
            "title_ru": rank.title_ru,
            "title_en": rank.title_en,
            "min_level": rank.min_level,
            "min_xp": rank.min_xp,
        }


@receiver(post_save, sender="users.User")
def create_user_profile(sender, instance, created, **kwargs):
    """Ensure a Profile is created for each new User."""
    if created:
        Profile.objects.create(user=instance)


class EmailVerificationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="verification_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)