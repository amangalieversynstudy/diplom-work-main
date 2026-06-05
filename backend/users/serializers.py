from game.models import ClassRole
from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    class_role = serializers.PrimaryKeyRelatedField(
        queryset=ClassRole.objects.all(), required=False, allow_null=True
    )
    # Стрик игрока: сырые счётчики + вычисляемые флаги для UI и напоминания.
    streak_active = serializers.ReadOnlyField()
    streak_at_risk = serializers.ReadOnlyField()

    class Meta:
        model = Profile
        fields = [
            "xp",
            "level",
            "bio",
            "class_role",
            "current_streak",
            "longest_streak",
            "streak_active",
            "streak_at_risk",
        ]
        read_only_fields = ("xp", "level", "current_streak", "longest_streak")
        ref_name = "UsersProfileSerializer"

    # Класс можно менять свободно — игроку даём возможность сменить путь
    # в любой момент (см. frontend/pages/class.jsx → /class).


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "display_name", "profile"]
