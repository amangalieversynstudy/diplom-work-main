"""Serializers for users and profile models."""

from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for the Profile model."""

    class_role = serializers.PrimaryKeyRelatedField(
        queryset=None, required=False, allow_null=True
    )

    class Meta:
        """Meta options for ProfileSerializer."""

        model = Profile
        fields = ["xp", "level", "bio", "class_role"]
        ref_name = "UsersProfileSerializer"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Late import to avoid circular import at module level
        from game.models import ClassRole

        self.fields["class_role"].queryset = ClassRole.objects.all()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model including nested profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        """Meta options for UserSerializer."""

        model = User
        fields = ["id", "username", "email", "display_name", "profile"]
