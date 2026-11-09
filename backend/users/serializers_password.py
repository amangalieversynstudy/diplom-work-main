"""Serializers for password reset flows."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

User = get_user_model()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset via email."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer used to validate token and set a new password."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate(self, attrs):
        """Validate uid and token and attach user to attrs on success."""
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except Exception:
            raise serializers.ValidationError("Invalid uid")
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid token")
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": list(error.messages)})
        attrs["user"] = user
        return attrs

    def save(self):
        """Set the new password and end every session: refresh tokens issued before the reset stop working."""
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        for token in OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True):
            BlacklistedToken.objects.get_or_create(token=token)
        return user
