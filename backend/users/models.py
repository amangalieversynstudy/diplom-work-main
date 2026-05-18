"""Custom user model and profile management."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class User(AbstractUser):
    """Custom user model with optional display name."""

    display_name = models.CharField(max_length=150, blank=True)


class Profile(models.Model):
    """Profile stores game-related user state such as XP and level."""

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

    def add_xp(self, amount):
        """Add XP to the profile and adjust level when thresholds are crossed."""
        self.xp += amount
        # simple leveling rule: every 100 XP = level up
        new_level = self.xp // 100 + 1
        if new_level > self.level:
            self.level = new_level
        self.save()


@receiver(post_save, sender="users.User")
def create_user_profile(sender, instance, created, **kwargs):
    """Ensure a Profile is created for each new User."""
    if created:
        Profile.objects.create(user=instance)
