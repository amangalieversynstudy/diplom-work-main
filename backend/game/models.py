"""Models for game entities: roles, locations, missions, and progress."""

from django.db import models
from django.utils import timezone


class ClassRole(models.Model):
    """A player class or role with an optional description."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        """Return human-readable name for ClassRole."""
        return self.name


class Location(models.Model):
    """A named location that contains missions."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        """Return human-readable title for Location."""
        return self.title


class Mission(models.Model):
    """A mission which can be completed by a user to gain XP."""

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="missions"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    xp_reward = models.IntegerField(default=10)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # CodeCombat-like gates
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="unlocks"
    )
    min_level = models.IntegerField(default=1)
    repeatable = models.BooleanField(default=False)
    repeat_xp_rate = models.IntegerField(
        default=0, help_text="Repeat completion XP in %, 0 = no XP on repeat"
    )

    def __str__(self):
        """Return human-readable title for Mission."""
        return self.title


class Progress(models.Model):
    """Tracks user progress for missions."""

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="progress"
    )
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    # Status and attempts like CodeCombat sessions
    completed = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=(
            ("not_started", "Not started"),
            ("in_progress", "In progress"),
            ("completed", "Completed"),
        ),
        default="not_started",
    )
    attempts = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    xp_earned = models.IntegerField(default=0)
    stars = models.SmallIntegerField(default=0)

    class Meta:
        unique_together = ("user", "mission")

    def start(self):
        """Mark mission as started: increment attempts and timestamps."""
        now = timezone.now()
        self.attempts = (self.attempts or 0) + 1
        if not self.started_at:
            self.started_at = now
        self.last_started_at = now
        if self.status != "completed":
            self.status = "in_progress"
        self.save()

    def complete(self):
        """Mark mission as completed with timestamp and status."""
        if not self.completed:
            self.completed = True
            self.status = "completed"
            self.completed_at = timezone.now()
            self.save()
