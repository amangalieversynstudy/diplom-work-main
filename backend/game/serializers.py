from rest_framework import serializers
from users.models import Profile

from .services import help_offer, public_task_data, sees_drafts
from .variants import personalize
from .models import (
    LeaderboardEntry,
    Location,
    Mission,
    MissionTask,
    Progress,
    Rank,
    TaskProgress,
    Track,
)


def _resolve_language(request, default="ru"):
    """Resolve preferred language from query params or headers."""
    if not request:
        return default
    lang = (
        request.query_params.get("lang")
        or request.headers.get("Accept-Language")
        or default
    )
    lang = lang.split(",")[0].split("-")[0].strip().lower()
    return lang if lang in {"ru", "en"} else default


class LocalizedSerializerMixin:
    """Подставляет локализованные title/description в выдачу."""

    language_field_name = "language"

    def _preferred_language(self):
        request = self.context.get("request") if hasattr(self, "context") else None
        return _resolve_language(request)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self._preferred_language()
        if hasattr(instance, "get_localized_title"):
            data["title"] = instance.get_localized_title(lang)
        if hasattr(instance, "get_localized_description"):
            data["description"] = instance.get_localized_description(lang)
        if self.language_field_name:
            data[self.language_field_name] = lang
        return data


class MissionTaskSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    language = serializers.SerializerMethodField()

    class Meta:
        model = MissionTask
        fields = [
            "id",
            "task_type",
            "order",
            "title",
            "title_en",
            "title_ru",
            "body",
            "body_en",
            "body_ru",
            "data",
            "xp_reward",
            "is_required",
            "estimated_minutes",
            "language",
        ]

    def get_language(self, obj):
        return self._preferred_language()

    def to_representation(self, instance):
        # a step with personal variants reads differently for every learner
        user = getattr(self.context.get("request"), "user", None)
        instance = personalize(instance, user.pk if user is not None and user.is_authenticated else None)
        data = super().to_representation(instance)
        # never send the answer key (correct_answer, expected_output ...)
        data["data"] = public_task_data(instance)
        return data


class MissionSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    track_id = serializers.SerializerMethodField()
    track_title = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    locked_reason = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()
    prerequisites = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    tasks = MissionTaskSerializer(many=True, read_only=True)

    class Meta:
        model = Mission
        fields = [
            "id",
            "title",
            "description",
            "title_en",
            "title_ru",
            "description_en",
            "description_ru",
            "xp_reward",
            "order",
            "is_active",
            "min_level",
            "repeatable",
            "repeat_xp_rate",
            "pos_x",
            "pos_y",
            "track_id",
            "track_title",
            "available",
            "locked_reason",
            "user_progress",
            "prerequisites",
            "tasks",
            "language",
        ]

    def get_locked_reason(self, obj):
        # why a mission is locked: None | "draft" | "level" | "prerequisites" (checked in this order)
        request = self.context.get("request")
        if not obj.is_active:
            return "draft"
        if request and request.user and request.user.is_authenticated:
            profile: Profile = getattr(request.user, "profile", None)
            if profile and profile.level < obj.min_level:
                return "level"
            # prerequisites must be completed
            if obj.prerequisites.exists():
                completed_missions = set(
                    Progress.objects.filter(
                        user=request.user, completed=True
                    ).values_list("mission_id", flat=True)
                )
                for pre in obj.prerequisites.all():
                    if pre.id not in completed_missions:
                        return "prerequisites"
        return None

    def get_available(self, obj):
        # доступность миссии: активна + level >= min_level + все prerequisites пройдены
        return self.get_locked_reason(obj) is None

    def get_user_progress(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            prog = (
                Progress.objects.filter(user=request.user, mission=obj)
                .values(
                    "completed",
                    "status",
                    "attempts",
                    "xp_earned",
                    "stars",
                    "completed_at",
                )
                .first()
            )
            return prog or {
                "completed": False,
                "status": "not_started",
                "attempts": 0,
                "xp_earned": 0,
                "stars": 0,
                "completed_at": None,
            }
        return None

    def get_track_id(self, obj):
        return obj.location.track_id

    def get_track_title(self, obj):
        # the course the mission belongs to: the map and the journey group by it
        track = obj.location.track
        return track.get_localized_title(self._preferred_language()) if track else ""

    def get_prerequisites(self, obj):
        # Compact representation for UI linking with localization
        lang = self._preferred_language()
        return [
            {"id": pre.id, "title": pre.get_localized_title(lang)}
            for pre in obj.prerequisites.all()
        ]

    def get_language(self, obj):
        return self._preferred_language()


class LocationSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    missions = serializers.SerializerMethodField()
    track = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id",
            "title",
            "description",
            "title_en",
            "title_ru",
            "description_en",
            "description_ru",
            "order",
            "track",
            "missions",
            "language",
        ]

    def get_missions(self, obj):
        # drafts are shown to the course owner and vetted staff only (filtered in Python to keep the prefetch)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        missions = [m for m in obj.missions.all() if m.is_active or sees_drafts(user, obj.track)]
        return MissionSerializer(missions, many=True, context=self.context).data

    def get_track(self, obj):
        track = obj.track
        if not track:
            return None
        lang = self._preferred_language()
        return {
            "id": track.id,
            "slug": track.slug,
            "title": track.get_localized_title(lang),
            "color_theme": track.color_theme,
        }

    def get_language(self, obj):
        return self._preferred_language()


class TrackSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    worlds = serializers.SerializerMethodField()
    tagline = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "title_en",
            "title_ru",
            "description_en",
            "description_ru",
            "tagline",
            "tagline_en",
            "tagline_ru",
            "icon_url",
            "banner_url",
            "color_theme",
            "order",
            "is_active",
            "worlds",
            "language",
        ]

    def get_worlds(self, obj):
        qs = obj.worlds.all().order_by("order")
        serializer = LocationSerializer(qs, many=True, context=self.context)
        return serializer.data

    def get_tagline(self, obj):
        return obj.get_localized_tagline(self._preferred_language())

    def get_language(self, obj):
        return self._preferred_language()


class ProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progress
        fields = [
            "id",
            "mission",
            "completed",
            "status",
            "attempts",
            "xp_earned",
            "stars",
            "started_at",
            "last_started_at",
            "completed_at",
        ]
        read_only_fields = fields


class TaskProgressSerializer(serializers.ModelSerializer):
    """Read-only view of a learner's task progress.

    Progress is written by the server only (see game.services): the client
    never sets status, attempts or score.
    """

    task_detail = MissionTaskSerializer(source="task", read_only=True)
    help_offer = serializers.SerializerMethodField()

    class Meta:
        model = TaskProgress
        fields = [
            "id",
            "task",
            "task_detail",
            "status",
            "attempts",
            "best_score",
            "last_submitted_at",
            "answer",
            "help_offer",
        ]
        read_only_fields = fields

    def get_help_offer(self, obj):
        return help_offer(obj)


class RankSerializer(serializers.ModelSerializer):
    language = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Rank
        fields = [
            "id",
            "slug",
            "title",
            "title_en",
            "title_ru",
            "description",
            "description_en",
            "description_ru",
            "min_level",
            "min_xp",
            "order",
            "icon_url",
            "language",
        ]

    def _preferred_language(self):
        request = self.context.get("request") if self.context else None
        return _resolve_language(request)

    def get_language(self, obj):
        return self._preferred_language()

    def get_title(self, obj):
        return obj.get_localized_title(self._preferred_language())

    def get_description(self, obj):
        return obj.get_localized_description(self._preferred_language())


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    track = serializers.SerializerMethodField()
    # Плоские поля для фронта (frontend/pages/leaderboard.jsx читает их
    # напрямую: user.xp, user.level, user.streak, user.username,
    # user.class_role). Дублируют user_display, чтобы не ломать
    # обратную совместимость с другими клиентами API.
    username = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    xp = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()
    class_role = serializers.SerializerMethodField()
    # the pk lets the client show the class under the same (translated) name as the class and
    # profile pages, instead of the single-language name stored in the database
    class_role_id = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardEntry
        fields = [
            "id",
            "user",
            "user_display",
            "username",
            "level",
            "xp",
            "streak",
            "class_role",
            "class_role_id",
            "track",
            "scope",
            "period_label",
            "xp_total",
            "position",
            "snapshot_at",
        ]

    def _profile(self, obj):
        return getattr(obj.user, "profile", None)

    @staticmethod
    def _closed_class_row(obj):
        """A class's own table shows the class to its members: no platform-wide level, XP, streak or hero class."""
        return obj.scope == "track" and obj.track is not None and not obj.track.is_public

    def get_user_display(self, obj):
        user = obj.user
        profile = self._profile(obj)
        if self._closed_class_row(obj):
            return {
                "id": user.id,
                "username": user.username,
                "display_name": getattr(user, "display_name", "") or user.username,
                "level": None,
                "xp": obj.xp_total or 0,
                "streak": None,
            }
        return {
            "id": user.id,
            "username": user.username,
            "display_name": getattr(user, "display_name", "") or user.username,
            "level": profile.level if profile else None,
            "xp": profile.xp if profile else None,
            "streak": self.get_streak(obj),
        }

    def get_username(self, obj):
        return getattr(obj.user, "display_name", "") or obj.user.username

    def get_level(self, obj):
        if self._closed_class_row(obj):
            return None
        p = self._profile(obj)
        return p.level if p else 1

    def get_xp(self, obj):
        # Строка курса ранжируется по XP этого курса, его и показываем: общий Profile.xp
        # в таблице курса читался бы как «очки за курс».
        if obj.scope != "global":
            return obj.xp_total or 0
        # xp_total общей строки отражает снепшот лидерборда, который может
        # отставать от текущего Profile.xp на пару секунд.
        # Берём максимум — фронту виден актуальный счёт сразу.
        p = self._profile(obj)
        return max(obj.xp_total or 0, p.xp if p else 0)

    def get_streak(self, obj):
        # оборванная серия показывается нулём везде (Profile.streak_active), и здесь тоже
        if self._closed_class_row(obj):
            return None
        p = self._profile(obj)
        return p.current_streak if p and p.streak_active else 0

    def get_class_role(self, obj):
        if self._closed_class_row(obj):
            return None
        p = self._profile(obj)
        cr = getattr(p, "class_role", None)
        return cr.name if cr else None

    def get_class_role_id(self, obj):
        if self._closed_class_row(obj):
            return None
        p = self._profile(obj)
        return getattr(p, "class_role_id", None)

    def get_track(self, obj):
        track = obj.track
        if not track:
            return None
        lang = _resolve_language(self.context.get("request"))
        return {
            "id": track.id,
            "slug": track.slug,
            "title": track.get_localized_title(lang),
            "color_theme": track.color_theme,
        }
