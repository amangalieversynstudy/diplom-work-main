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
    is_intro = models.BooleanField(
        default=False,
        help_text=(
            "Вводный курс. Пока пользователь не пройдёт все миссии "
            "этого трека, выбор класса заблокирован. "
            "Включать стоит ровно у одного активного трека."
        ),
    )
    owner = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_tracks",
        help_text=(
            "Преподаватель-владелец курса (Студия). Пусто = системный/seed-курс, "
            "редактируется только суперюзером."
        ),
    )

    is_public = models.BooleanField(
        default=True,
        help_text=(
            "Виден всем ученикам. Выключено = «класс»: курс видят только вошедшие по коду "
            "и сам преподаватель. Новые курсы Студии создаются закрытыми."
        ),
    )
    join_code = models.CharField(
        max_length=12, unique=True, null=True, blank=True,
        help_text="Код класса: ученик вводит его или открывает ссылку /join/<код>.",
    )
    join_open = models.BooleanField(
        default=True, help_text="Принимает ли класс новых учеников по коду."
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.get_localized_title()

    @classmethod
    def get_intro(cls):
        """Return the single active intro track, or None if not configured."""
        return cls.objects.filter(is_intro=True, is_active=True).first()

    def is_completed_by(self, user) -> bool:
        """True if `user` has completed every active mission in this track.

        Fail-open: a track with no missions is treated as already complete,
        so a misconfigured intro track never strands users on a locked page.
        """
        mission_ids = set(
            Mission.objects
            .filter(location__track=self, is_active=True)
            .values_list("id", flat=True)
        )
        if not mission_ids:
            return True
        completed_ids = set(
            Progress.objects
            .filter(user=user, mission_id__in=mission_ids, completed=True)
            .values_list("mission_id", flat=True)
        )
        return mission_ids.issubset(completed_ids)

    def completion_progress(self, user) -> dict:
        """Return {completed, total} for active missions in this track."""
        total = Mission.objects.filter(location__track=self, is_active=True).count()
        done = Progress.objects.filter(
            user=user,
            mission__location__track=self,
            mission__is_active=True,
            completed=True,
        ).count()
        return {"completed": done, "total": total}

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


class Enrollment(models.Model):
    """A learner who joined a teacher's class (a closed course) with its code, and agreed to be seen there."""

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="enrollments"
    )
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="enrollments")
    joined_at = models.DateTimeField(auto_now_add=True)
    consented_at = models.DateTimeField(
        help_text="Когда ученик согласился, что преподаватель видит его ник и прогресс в этом курсе."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "track"], name="one_enrollment_per_user_and_track")
        ]
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user_id} in {self.track_id}"


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

    class Meta:
        ordering = ["mission", "order", "id"]

    def __str__(self):
        return f"{self.mission_id}:{self.order}:{self.get_localized_title()}"

    @property
    def kind(self):
        """What the analytics call this step: "explain" for the question about a learner's own code
        (a quiz marked ``data.kind = "explain"``), otherwise the task type."""
        data = self.data if isinstance(self.data, dict) else {}
        return "explain" if self.task_type == "quiz" and data.get("kind") == "explain" else self.task_type

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
        """Mark mission as completed with timestamp and status.

        On the first completion we also register the day in the player's
        streak (Profile.register_activity): this is the single place a
        mission is marked done (views call prog.complete()), so the streak,
        the streak_7 achievement and the leaderboard/analytics streak
        columns all stay in sync from here.
        """
        if not self.completed:
            self.completed = True
            self.status = "completed"
            self.completed_at = timezone.now()
            self.save()
            from .classes import pays_globally

            profile = getattr(self.user, "profile", None)
            # the streak is global: a teacher's trial run or a class whose XP stays inside it does not move it
            if profile and pays_globally(self.user, self.mission.location.track if self.mission.location_id else None):
                profile.register_activity()


class UserAchievement(models.Model):
    """A single achievement unlocked by a user.

    Only the *unlock fact* is persisted (user + slug + timestamp). The
    achievement catalog itself — titles, descriptions, icons, conditions —
    lives in code (``game/achievements.py``) and is localized on the frontend.
    This keeps the feature migration-light: adding a new achievement never
    touches the database, and conditions can be tuned without data migrations.
    """

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="achievements"
    )
    slug = models.CharField(max_length=64)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "slug")
        ordering = ["earned_at"]

    def __str__(self):
        return f"{self.user_id}:{self.slug}"


class CodeRun(models.Model):
    """One run of a learner's code in the sandbox.

    The raw material for "attempts to success" and error analytics. Only
    measurements are stored (sizes, exit code, error class), never the code or
    its output: the last attempted code already lives in ``TaskProgress.answer``.
    """

    OUTCOMES = (
        ("success", "Ran and (if graded) passed"),
        ("wrong_output", "Ran fine but the output did not match"),
        ("error", "Crashed or exited with a non-zero code"),
        ("timeout", "Killed by the time limit"),
        ("output_limit", "Killed for printing too much"),
        ("runner_error", "Sandbox failure, not the learner's fault"),
    )

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="code_runs"
    )
    task = models.ForeignKey(
        MissionTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="code_runs",
        help_text="Empty for free practice runs outside a task.",
    )
    outcome = models.CharField(max_length=16, choices=OUTCOMES)
    error_type = models.CharField(
        max_length=64, blank=True, help_text="Exception class, e.g. NameError."
    )
    error_message = models.CharField(max_length=200, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    code_length = models.PositiveIntegerField(default=0)
    stdout_size = models.PositiveIntegerField(default=0)
    stderr_size = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(
        null=True, blank=True, help_text="Null when the run was not graded."
    )
    attempt_no = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="The task's attempt counter after this run (graded runs only).",
    )
    after_solved = models.BooleanField(
        default=False,
        help_text="The task was already solved before this run (re-run for fun): "
        "leave such runs out of 'attempts to success'.",
    )
    provenance = models.JSONField(
        default=dict,
        blank=True,
        help_text="How the code got into the editor (counts only, never the keystrokes): "
        "pasted_chars, typed_chars, paste_count, edit_events, edits_after_paste, elapsed_ms. "
        "Sent by the editor, so a hint at authorship and not a proof.",
    )
    fingerprint = models.CharField(
        max_length=32,
        blank=True,
        db_index=True,
        help_text="Hash of the code's structure with the author's own names, comments and "
        "docstrings left out (game/codeanalysis.py). The code itself is not kept in this table.",
    )
    ast_nodes = models.PositiveIntegerField(default=0, help_text="Size of the parsed code, 0 if it did not parse.")
    constructs = models.JSONField(
        default=list, blank=True, help_text="Language constructs used: def, lambda, comprehension, try, ..."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["task", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.task_id}:{self.outcome}"


class LearningEvent(models.Model):
    """Timeline of what a learner did (the behavioural footprint).

    Code runs live in :class:`CodeRun`; quiz/story submissions, hints, AI
    mentor calls, logins and mission milestones are recorded here.
    """

    LOGIN = "login"
    MISSION_STARTED = "mission_started"
    MISSION_COMPLETED = "mission_completed"
    TASK_OPENED = "task_opened"
    TASK_SUBMITTED = "task_submitted"
    HINT_USED = "hint_used"
    SKELETON_USED = "skeleton_used"
    AI_HINT_USED = "ai_hint_used"
    AI_MENTOR_USED = "ai_mentor_used"
    HELP_OFFERED = "help_offered"
    HELP_RESCUE = "help_rescue"

    TYPES = (
        (LOGIN, "Login"),
        (MISSION_STARTED, "Mission started"),
        (MISSION_COMPLETED, "Mission completed"),
        (TASK_OPENED, "Task opened"),
        (TASK_SUBMITTED, "Story/quiz step submitted"),
        (HINT_USED, "Hint scroll used"),
        (SKELETON_USED, "Skeleton scroll used"),
        (AI_HINT_USED, "AI hint used"),
        (AI_MENTOR_USED, "AI mentor used"),
        (HELP_OFFERED, "Help offered after repeated failures"),
        (HELP_RESCUE, "Free rescue hint (no items left)"),
    )

    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="learning_events"
    )
    event_type = models.CharField(max_length=32, choices=TYPES)
    task = models.ForeignKey(
        MissionTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_events",
    )
    mission = models.ForeignKey(
        Mission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_events",
    )
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.event_type}"


class FreshnessSample(models.Model):
    """One measurement of how stale the teacher's live panel was ("data freshness").

    Written when a teacher's open panel asks for fresh data and there are learner actions it has not shown
    yet: ``lag`` of an action = the moment the panel received it minus the moment the learner did it. Only
    numbers are kept; the actions themselves stay in :class:`LearningEvent` / :class:`CodeRun`.
    """

    viewer = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="freshness_samples")
    polled_at = models.DateTimeField(db_index=True)
    new_events = models.PositiveIntegerField()
    lag_mean_s = models.FloatField()
    lag_max_s = models.FloatField()

    class Meta:
        ordering = ["-polled_at"]

    def __str__(self):
        return f"{self.viewer_id}@{self.polled_at:%H:%M:%S}: {self.new_events} events, mean {self.lag_mean_s:.1f}s"


class UsabilityResponse(models.Model):
    """A teacher's answers to the System Usability Scale about the dashboard ("convenience for the teacher").

    ``answers`` are the ten ratings 1-5 in the questionnaire's order; ``score`` is the SUS score 0-100
    (Brooke, 1996; about 68 is the average). A teacher may answer again: the latest answer counts.
    """

    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="usability_responses")
    answers = models.JSONField()
    score = models.FloatField()
    comment = models.CharField(max_length=1000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}: SUS {self.score:.1f}"


class EarlyWarningSnapshot(models.Model):
    """The early-warning list as it stood on one day (the data behind hypothesis H3).

    The list is computed on demand and nothing else keeps yesterday's version, so "were the learners marked
    urgent the ones who left?" could not be answered afterwards. One row per learner per day, written once a
    day by ``snapshot_early_warning``; only learners who agreed to the research (``research_consent``) are
    stored, and only the level, score and reason *codes* (no names, steps or code).
    """

    date = models.DateField(db_index=True)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="warning_snapshots")
    level = models.CharField(max_length=8)  # high | medium | ok
    score = models.PositiveSmallIntegerField(default=0)
    reasons = models.JSONField(default=list, blank=True)  # codes only: stuck_task, inactive, model_risk
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "user_id"]
        constraints = [
            models.UniqueConstraint(fields=["date", "user"], name="one_warning_snapshot_per_learner_per_day"),
        ]

    def __str__(self):
        return f"{self.date}:{self.user_id}:{self.level}"
