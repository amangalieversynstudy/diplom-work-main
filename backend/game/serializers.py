"""Serializers for game models used in API endpoints."""

from rest_framework import serializers

from .models import Location, Mission, Progress
from users.models import Profile


class MissionSerializer(serializers.ModelSerializer):
    """Serializer for Mission model."""

    available = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()

    class Meta:
        """Meta options for MissionSerializer."""

        model = Mission
        fields = [
            "id",
            "title",
            "description",
            "xp_reward",
            "order",
            "is_active",
            "min_level",
            "repeatable",
            "repeat_xp_rate",
            "available",
            "user_progress",
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
                    Progress.objects.filter(user=request.user, completed=True).values_list(
                        "mission_id", flat=True
                    )
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


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for Location, includes nested missions."""

    missions = MissionSerializer(many=True, read_only=True)

    class Meta:
        """Meta options for LocationSerializer."""

        model = Location
        fields = ["id", "title", "description", "order", "missions"]


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
