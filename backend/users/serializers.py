"""Serializers for users and profile models."""

from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for the Profile model."""

    class Meta:
        """Meta options for ProfileSerializer."""

        model = Profile
        fields = ["xp", "level", "bio"]
        ref_name = "UsersProfileSerializer"


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model including nested profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        """Meta options for UserSerializer."""

        model = User
        fields = ["id", "username", "email", "display_name", "profile"]
