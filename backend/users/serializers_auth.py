"""Authentication-related serializers for user registration and detail views.

Файл содержит минимальные сериализаторы для регистрации и просмотра
пользователя, используемые в API аутентификации.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer used to register new users.

    Fields: id, username, email, password (write-only).
    """

    password = serializers.CharField(write_only=True)

    class Meta:
        """Meta for RegisterSerializer."""

        model = User
        fields = ("id", "username", "email", "password")

    def validate_email(self, value):
        """Ensure email is unique across all users."""
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Этот email уже используется.")
        return value

    def create(self, validated_data):
        """Create a new User instance from validated data."""
        # Ensure username is unique with clear validation error
        username = validated_data["username"]
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "Это имя пользователя уже занято."})
        email = validated_data.get("email") or ""
        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data["password"],
        )
        return user


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile used in authentication flows."""

    class Meta:
        """Meta options for ProfileSerializer used in auth."""

        model = Profile
        fields = ("xp", "level", "bio")
        ref_name = "AuthProfileSerializer"


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user serializer including profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        """Meta for user detail serializer."""

        model = User
        fields = ("id", "username", "email", "profile")
