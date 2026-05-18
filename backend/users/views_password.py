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
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "If the email exists, a reset link will be sent."}
            )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"/reset-password-confirm/?uid={uid}&token={token}"
        send_mail("Password reset", f"Reset link: {reset_link}", None, [email])
        return Response({"detail": "If the email exists, a reset link will be sent."})


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
