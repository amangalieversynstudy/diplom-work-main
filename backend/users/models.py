"""Custom user model and profile management."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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