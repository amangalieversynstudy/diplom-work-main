from game.models import ClassRole
from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    class_role = serializers.PrimaryKeyRelatedField(
        queryset=ClassRole.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Profile
        fields = ["xp", "level", "bio", "class_role"]
        read_only_fields = ("xp", "level")
        ref_name = "UsersProfileSerializer"

    # Класс можно менять свободно — игроку даём возможность сменить путь
    # в любой момент (см. frontend/pages/class.jsx → /class).


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "display_name", "profile"]
