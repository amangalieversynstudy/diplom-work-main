from rest_framework import serializers
from .models import Location, Mission, Progress


class MissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mission
        fields = ["id", "title", "description", "xp_reward", "order", "is_active"]


class LocationSerializer(serializers.ModelSerializer):
    missions = MissionSerializer(many=True, read_only=True)

    class Meta:
        model = Location
        fields = ["id", "title", "description", "order", "missions"]


class ProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progress
        fields = ["id", "mission", "completed", "completed_at"]
