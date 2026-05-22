"""Сериализаторы для регистрации и просмотра пользователя."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Этот email уже используется.")
        return value

    def validate_password(self, value):
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError("; ".join(e.messages))
        return value

    def create(self, validated_data):
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
    class Meta:
        model = Profile
        fields = ("xp", "level", "bio")
        ref_name = "AuthProfileSerializer"


class UserDetailSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "profile")
