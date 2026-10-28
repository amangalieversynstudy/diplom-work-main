"""Сериализаторы для регистрации и просмотра пользователя."""

import hmac

from django.conf import settings
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Profile
from .validators import clean_single_email, clean_username

User = get_user_model()


def email_verification_works():
    """Do letters really go out? Not under DEBUG and not with the console backend (then accounts are activated at
    once, see RegisterView). Rules that depend on a confirmed address apply only when this is true."""
    return not getattr(settings, "DEBUG", False) and "console" not in getattr(settings, "EMAIL_BACKEND", "")


def _invite_form(value):
    """The code as typed by hand: case, spaces and dashes do not matter ("pilot 2026" is "PILOT-2026")."""
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def invite_code_matches(value):
    """Is *value* the teacher invite code (settings.TEACHER_INVITE_CODE)? Never true when the code is switched off.
    Compared in constant time as bytes: a non-ASCII str would make ``compare_digest`` raise (a 500)."""
    expected = _invite_form(getattr(settings, "TEACHER_INVITE_CODE", ""))
    given = _invite_form(value)
    return bool(expected and given) and hmac.compare_digest(given.encode(), expected.encode())


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    # Optional teacher invite code (see invite_code_matches): the right one gives the self-service teacher role.
    # Never returned in a response.
    teacher_code = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=64
    )

    # Who is signing up. "teacher" gives the self-service teacher role (cabinet, analytics, Studio for the
    # person's OWN courses only); it is open unless TEACHER_SELF_REGISTRATION is switched off.
    role = serializers.ChoiceField(
        choices=("student", "teacher"), write_only=True, required=False, default="student"
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
            "role",
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
        wants_teacher_role = validated_data.pop("role", "student") == "teacher"
        username = validated_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError({"username": "Это имя пользователя уже занято."})
        email = validated_data.get("email") or ""

        # A given code must be the server's one; a switched-off code (empty) rejects every code. The code is the
        # trust anchor, so a teacher with it needs no open sign-up and no e-mail.
        has_code = False
        if teacher_code:
            if not invite_code_matches(teacher_code):
                raise serializers.ValidationError(
                    {"teacher_code": "Неверный код преподавателя. Его выдаёт организатор пилота."}
                )
            has_code = True
        elif wants_teacher_role and not getattr(settings, "TEACHER_SELF_REGISTRATION", True):
            raise serializers.ValidationError(
                {"teacher_code": "Введите код преподавателя: без него регистрация преподавателей закрыта."}
            )
        elif (
            wants_teacher_role
            and getattr(settings, "TEACHER_REQUIRE_EMAIL", False)
            and email_verification_works()
            and not email
        ):
            # the account then stays inactive until the link in the letter is opened (RegisterView)
            raise serializers.ValidationError(
                {"email": "Преподавателю нужен e-mail: на него придёт ссылка для активации."}
            )

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=validated_data["password"],
                )
        except IntegrityError:  # the same name taken by a parallel sign-up: an answer, not a 500
            raise serializers.ValidationError({"username": "Это имя пользователя уже занято."})
        if has_code or wants_teacher_role:
            user.is_teacher = True
            user.save(update_fields=["is_teacher"])
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
