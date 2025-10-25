"""Serializers for game models used in API endpoints."""

from rest_framework import serializers

from .models import Location, Mission, Progress


class MissionSerializer(serializers.ModelSerializer):
    """Serializer for Mission model."""

    class Meta:
        """Meta options for MissionSerializer."""

        model = Mission
        fields = ["id", "title", "description", "xp_reward", "order", "is_active"]


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
        fields = ["id", "mission", "completed", "completed_at"]
