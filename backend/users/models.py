from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)


class Profile(models.Model):
    user = models.OneToOneField(
        "users.User", on_delete=models.CASCADE, related_name="profile"
    )
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    bio = models.TextField(blank=True)

    def add_xp(self, amount):
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
