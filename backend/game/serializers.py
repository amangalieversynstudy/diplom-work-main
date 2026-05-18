"""Serializers for game models used in API endpoints."""

from rest_framework import serializers
from users.models import Profile

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
    """Inject localized title/description fields."""

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
            "is_side_quest",
            "estimated_minutes",
            "language",
        ]

    def get_language(self, obj):
        return self._preferred_language()


class MissionSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Mission model."""

    available = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()
    prerequisites = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    tasks = MissionTaskSerializer(many=True, read_only=True)

    class Meta:
        """Meta options for MissionSerializer."""

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
            "available",
            "user_progress",
            "prerequisites",
            "tasks",
            "language",
        ]

    def get_available(self, obj):
        """Mission availability: check level, prerequisites and active flag."""
        request = self.context.get("request")
        if not obj.is_active:
            return False
        if request and request.user and request.user.is_authenticated:
            profile: Profile = getattr(request.user, "profile", None)
            if profile and profile.level < obj.min_level:
                return False
            # prerequisites must be completed
            if obj.prerequisites.exists():
                completed_missions = set(
                    Progress.objects.filter(
                        user=request.user, completed=True
                    ).values_list("mission_id", flat=True)
                )
                for pre in obj.prerequisites.all():
                    if pre.id not in completed_missions:
                        return False
        return True

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
    """Serializer for Location, includes nested missions."""

    missions = MissionSerializer(many=True, read_only=True)
    track = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()

    class Meta:
        """Meta options for LocationSerializer."""

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
            "is_premium": track.is_premium,
        }

    def get_language(self, obj):
        return self._preferred_language()


class TrackSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    """Serializer for Track with nested worlds."""

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
            "is_premium",
            "default_language",
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

    def get_language(self, obj):
        return self._preferred_language()


class ProgressSerializer(serializers.ModelSerializer):
    """Serializer for Progress model."""

    class Meta:
        """Meta options for ProgressSerializer."""

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


class TaskProgressSerializer(serializers.ModelSerializer):
    """Serializer for TaskProgress entries."""

    task_detail = MissionTaskSerializer(source="task", read_only=True)
    task = serializers.PrimaryKeyRelatedField(
        queryset=MissionTask.objects.all(), write_only=False
    )

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
        ]


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

    class Meta:
        model = LeaderboardEntry
        fields = [
            "id",
            "user",
            "user_display",
            "track",
            "scope",
            "period_label",
            "xp_total",
            "position",
            "snapshot_at",
        ]

    def get_user_display(self, obj):
        user = obj.user
        profile = getattr(user, "profile", None)
        return {
            "id": user.id,
            "username": user.username,
            "display_name": getattr(user, "display_name", "") or user.username,
            "level": profile.level if profile else None,
            "xp": profile.xp if profile else None,
        }

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
