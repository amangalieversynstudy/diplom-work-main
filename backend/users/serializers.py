"""Serializers for users and profile models."""

from game.models import ClassRole
from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for the Profile model."""

    class_role = serializers.PrimaryKeyRelatedField(
        queryset=ClassRole.objects.all(), required=False, allow_null=True
    )

    class Meta:
        """Meta options for ProfileSerializer."""

        model = Profile
        fields = ["xp", "level", "bio", "class_role"]
        read_only_fields = ("xp", "level")
        ref_name = "UsersProfileSerializer"

    def validate_class_role(self, value):
        """Prevent reassigning a class once it has been selected."""
        profile = getattr(self, "instance", None)
        if profile and profile.class_role_id:
            if value is None or value.id != profile.class_role_id:
                raise serializers.ValidationError(
                    "Class role can be selected only once for this profile."
                )
        return value


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model including nested profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        """Meta options for UserSerializer."""

        model = User
        fields = ["id", "username", "email", "display_name", "profile"]
