"""Views for requesting password reset and confirming new password."""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.response import Response

from .serializers_password import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)

User = get_user_model()


class PasswordResetRequestView(generics.GenericAPIView):
    """Accepts an email and sends a password reset link if the user exists."""

    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        """Handle password reset request by email."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        # Один и тот же ответ независимо от того, есть ли такой email —
        # чтобы не раскрывать, какие адреса зарегистрированы.
        generic = Response(
            {
                "detail": (
                    "Если такой email зарегистрирован, "
                    "мы отправили ссылку для сброса пароля."
                )
            }
        )
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return generic

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        import os

        from django.conf import settings

        frontend_url = (
            getattr(settings, "FRONTEND_URL", None)
            or os.environ.get("FRONTEND_URL")
            or "http://localhost:3000"
        )
        reset_link = (
            f"{frontend_url.rstrip('/')}/reset-password-confirm?uid={uid}&token={token}"
        )
        try:
            send_mail(
                "Сброс пароля — RPG Academy",
                (
                    f"Привет, {user.username}!\n\n"
                    "Кто-то запросил сброс пароля для твоего аккаунта.\n"
                    "Перейди по ссылке, чтобы задать новый пароль:\n"
                    f"{reset_link}\n\n"
                    "Если это был не ты — просто проигнорируй письмо, "
                    "пароль останется прежним."
                ),
                None,
                [email],
            )
        except Exception as e:
            import logging
            logging.error("[PASSWORD-RESET] Email send failed for %s: %r", email, e)
        return generic


class PasswordResetConfirmView(generics.GenericAPIView):
    """Accepts a uid/token and new password to reset the user's password."""

    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        """Validate token and set new password for the user."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been reset."}, status=status.HTTP_200_OK
        )
