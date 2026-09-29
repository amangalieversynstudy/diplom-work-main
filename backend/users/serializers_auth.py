"""Сериализаторы для регистрации и просмотра пользователя."""

import hmac

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Profile
from .validators import clean_single_email, clean_username

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    # Необязательный код преподавателя. Верный код → аккаунт получает is_staff
    # (доступ к аналитике и кабинету). Никогда не возвращается в ответе.
    teacher_code = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    # Opt-in consent to use this learner's activity in research. Off unless
    # the sign-up form sends true.
    research_consent = serializers.BooleanField(
        write_only=True, required=False, default=False
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "teacher_code",
            "research_consent",
        )

    def validate_username(self, value):
        try:
            return clean_username(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(" ".join(error.messages))

    def validate_email(self, value):
        if value:
            try:
                value = clean_single_email(value)
            except DjangoValidationError as error:
                raise serializers.ValidationError(" ".join(error.messages))
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
        teacher_code = (validated_data.pop("teacher_code", "") or "").strip()
        research_consent = validated_data.pop("research_consent", False)
        username = validated_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({"username": "Это имя пользователя уже занято."})
        email = validated_data.get("email") or ""

        # Если указан код преподавателя — он должен совпасть с серверным
        # секретом. Пустой серверный код = регистрация преподавателей выключена,
        # поэтому любой переданный код отвергаем (нельзя выдать is_staff молча).
        is_teacher = False
        if teacher_code:
            expected = getattr(settings, "TEACHER_INVITE_CODE", "") or ""
            if not expected or not hmac.compare_digest(teacher_code, expected):
                raise serializers.ValidationError(
                    {"teacher_code": "Неверный код преподавателя."}
                )
            is_teacher = True

        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data["password"],
        )
        if is_teacher:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        if research_consent:
            profile = user.profile
            profile.set_research_consent(True)
            profile.save(update_fields=["research_consent", "research_consent_at"])
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
