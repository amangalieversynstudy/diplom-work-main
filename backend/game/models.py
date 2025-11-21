"""Models for game entities: roles, locations, missions, and progress."""

from django.db import models
from django.utils import timezone


class Track(models.Model):
    """Learning track (e.g., Python Path, Django Path)."""

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    title_ru = models.CharField(max_length=200, blank=True)
    description_en = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
    tagline_en = models.CharField(max_length=255, blank=True)
    tagline_ru = models.CharField(max_length=255, blank=True)
    icon_url = models.URLField(blank=True)
    banner_url = models.URLField(blank=True)
    color_theme = models.CharField(max_length=32, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_premium = models.BooleanField(default=False)
    default_language = models.CharField(max_length=5, default="ru")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.get_localized_title()

    def _get_localized_value(self, field_name: str, lang: str = "ru") -> str:
        lang = (lang or "ru").lower()
        if lang not in {"ru", "en"}:
            lang = "ru"
        localized = getattr(self, f"{field_name}_{lang}", "") or ""
        if localized.strip():
            return localized
        fallback = getattr(self, field_name, "") or ""
        if fallback.strip():
            return fallback
        other_lang = "en" if lang == "ru" else "ru"
        return getattr(self, f"{field_name}_{other_lang}", "") or ""

    def get_localized_title(self, lang: str = "ru") -> str:
        return self._get_localized_value("title", lang)

    def get_localized_description(self, lang: str = "ru") -> str:
        return self._get_localized_value("description", lang)

    def get_localized_tagline(self, lang: str = "ru") -> str:
        return self._get_localized_value("tagline", lang)


class ClassRole(models.Model):
    """A player class or role with an optional description."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        """Return human-readable name for ClassRole."""
        return self.name


class Location(models.Model):
    """A named location that contains missions."""

    track = models.ForeignKey(
        Track, on_delete=models.CASCADE, related_name="worlds", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    title_ru = models.CharField(max_length=200, blank=True)
    description_en = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        """Return human-readable title for Location."""
        return self.get_localized_title()

    def _get_localized_value(self, field_name: str, lang: str = "ru") -> str:
        lang = (lang or "ru").lower()
        if lang not in {"ru", "en"}:
            lang = "ru"
        localized = getattr(self, f"{field_name}_{lang}", "") or ""
        if localized.strip():
            return localized
        fallback = getattr(self, field_name, "") or ""
        if fallback.strip():
            return fallback
        # fallback to the other language if available
        other_lang = "en" if lang == "ru" else "ru"
        return getattr(self, f"{field_name}_{other_lang}", "") or ""

    def get_localized_title(self, lang: str = "ru") -> str:
        """Return title for requested language with sensible fallbacks."""
        return self._get_localized_value("title", lang)

    def get_localized_description(self, lang: str = "ru") -> str:
        """Return description for requested language with sensible fallbacks."""
        return self._get_localized_value("description", lang)


class Mission(models.Model):
    """A mission which can be completed by a user to gain XP."""

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="missions"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    title_ru = models.CharField(max_length=200, blank=True)
    description_en = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
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
    # Позиция ноды на карте (в процентах по контейнеру 0..100)
    pos_x = models.IntegerField(default=0)
    pos_y = models.IntegerField(default=0)

    def __str__(self):
        """Return human-readable title for Mission."""
        return self.get_localized_title()

    def _get_localized_value(self, field_name: str, lang: str = "ru") -> str:
        lang = (lang or "ru").lower()
        if lang not in {"ru", "en"}:
            lang = "ru"
        localized = getattr(self, f"{field_name}_{lang}", "") or ""
        if localized.strip():
            return localized
        fallback = getattr(self, field_name, "") or ""
        if fallback.strip():
            return fallback
        other_lang = "en" if lang == "ru" else "ru"
        return getattr(self, f"{field_name}_{other_lang}", "") or ""

    def get_localized_title(self, lang: str = "ru") -> str:
        """Return mission title for requested language."""
        return self._get_localized_value("title", lang)

    def get_localized_description(self, lang: str = "ru") -> str:
        """Return mission description for requested language."""
        return self._get_localized_value("description", lang)


class MissionTask(models.Model):
    """Granular task/step inside a mission (Story, Quiz, Code, Project)."""

    TASK_TYPES = (
        ("story", "Story/Theory"),
        ("quiz", "Quiz"),
        ("code", "Code"),
        ("project", "Project"),
        ("challenge", "Challenge"),
    )

    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name="tasks"
    )
    order = models.IntegerField(default=0)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default="story")
    title = models.CharField(max_length=255, blank=True)
    title_en = models.CharField(max_length=255, blank=True)
    title_ru = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    body_en = models.TextField(blank=True)
    body_ru = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    xp_reward = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True)
    estimated_minutes = models.IntegerField(default=5)
    is_side_quest = models.BooleanField(
        default=False,
        help_text="Если True — отображается как побочная миссия для доп. XP",
    )

    class Meta:
        ordering = ["mission", "order", "id"]

    def __str__(self):
        return f"{self.mission_id}:{self.order}:{self.get_localized_title()}"

    def _get_localized_value(self, field_name: str, lang: str = "ru") -> str:
        lang = (lang or "ru").lower()
        if lang not in {"ru", "en"}:
            lang = "ru"
        localized = getattr(self, f"{field_name}_{lang}", "") or ""
        if localized.strip():
            return localized
        fallback = getattr(self, field_name, "") or ""
        if fallback.strip():
            return fallback
        other_lang = "en" if lang == "ru" else "ru"
        return getattr(self, f"{field_name}_{other_lang}", "") or ""

    def get_localized_title(self, lang: str = "ru") -> str:
        return self._get_localized_value("title", lang)

    def get_localized_body(self, lang: str = "ru") -> str:
        return self._get_localized_value("body", lang)


class TaskProgress(models.Model):
    """Tracks user-level progress for each mission task."""

    STATUS_CHOICES = (
        ("not_started", "Not started"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
    )

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="task_progress"
    )
    task = models.ForeignKey(
        MissionTask, on_delete=models.CASCADE, related_name="progress_entries"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started")
    attempts = models.IntegerField(default=0)
    best_score = models.IntegerField(default=0)
    last_submitted_at = models.DateTimeField(null=True, blank=True)
    answer = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("user", "task")

    def mark_attempt(self, score: int = 0, completed: bool = False):
        now = timezone.now()
        self.attempts = (self.attempts or 0) + 1
        self.last_submitted_at = now
        self.best_score = max(self.best_score or 0, score or 0)
        if completed:
            self.status = "completed"
        elif self.status == "not_started":
            self.status = "in_progress"
        self.save()


class Rank(models.Model):
    """XP-based rank ladder (Novice -> Python Master -> Junior Django Dev)."""

    slug = models.SlugField(unique=True)
    title_en = models.CharField(max_length=200)
    title_ru = models.CharField(max_length=200)
    description_en = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
    min_level = models.IntegerField(default=1)
    min_xp = models.IntegerField(default=0)
    order = models.IntegerField(default=0)
    icon_url = models.URLField(blank=True)

    class Meta:
        ordering = ["order", "min_level", "min_xp"]

    def __str__(self):
        return f"{self.slug} ({self.title_en})"

    def get_localized_title(self, lang: str = "ru") -> str:
        lang = (lang or "ru").lower()
        if lang not in {"ru", "en"}:
            lang = "ru"
        return getattr(self, f"title_{lang}", self.title_ru or self.title_en)

    def get_localized_description(self, lang: str = "ru") -> str:
        lang = (lang or "ru").lower()
        if lang not in {"ru", "en"}:
            lang = "ru"
        return getattr(self, f"description_{lang}", "")


class LeaderboardEntry(models.Model):
    """Snapshot of XP leaderboard for track/global scopes."""

    SCOPE_CHOICES = (
        ("global", "Global"),
        ("track", "Track"),
        ("friends", "Friends"),
    )

    track = models.ForeignKey(
        Track, on_delete=models.CASCADE, null=True, blank=True, related_name="leaderboard"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="leaderboard_entries"
    )
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default="global")
    period_label = models.CharField(
        max_length=32,
        default="all_time",
        help_text="Например: all_time, weekly_2025W46, monthly_2025-11",
    )
    xp_total = models.IntegerField(default=0)
    position = models.IntegerField(default=0)
    snapshot_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scope", "track_id", "period_label", "position"]
        unique_together = ("track", "user", "scope", "period_label")

    def __str__(self):
        track_slug = self.track.slug if self.track else "global"
        return f"{self.scope}:{track_slug}:{self.user_id} -> {self.xp_total}"


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
