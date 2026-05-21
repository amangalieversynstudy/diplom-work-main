"""Authentication views for register, login, logout and email verification."""

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Token views are imported where needed; keep imports local in views that use them
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers_auth import RegisterSerializer, UserDetailSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Endpoint to register new users and send verification email."""

    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        """Create the user and attempt to send a verification email."""
        user = serializer.save()
        # Новый аккаунт неактивен до перехода по ссылке из письма
        user.is_active = False
        user.save(update_fields=["is_active"])

        # send verification email (console backend in dev)
        try:
            import os

            from django.conf import settings
            from django.contrib.auth.tokens import default_token_generator
            from django.core.mail import send_mail
            from django.utils.encoding import force_bytes
            from django.utils.http import urlsafe_base64_encode

            if user.email:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                frontend_url = (
                    getattr(settings, "FRONTEND_URL", None)
                    or os.environ.get("FRONTEND_URL")
                    or "http://localhost:3000"
                )
                verify_link = (
                    f"{frontend_url.rstrip('/')}/verify-email?uid={uid}&token={token}"
                )
                send_mail(
                    "Подтверждение email — RPG Academy",
                    (
                        f"Привет, {user.username}!\n\n"
                        "Перейди по ссылке, чтобы активировать аккаунт:\n"
                        f"{verify_link}\n\n"
                        "Если ты не регистрировался — проигнорируй это письмо."
                    ),
                    None,
                    [user.email],
                )
        except Exception:
            # don't fail registration if email backend misconfigured
            pass

    def create(self, request, *args, **kwargs):
        """Return JSON with created user payload and 201 status."""
        response = super().create(request, *args, **kwargs)
        return Response(response.data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveAPIView):
    """Return details about the currently authenticated user."""

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserDetailSerializer

    def get_object(self):
        """Return the currently authenticated user."""
        return self.request.user


class LogoutView(APIView):
    """Blacklist refresh token to logout a user."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        """Blacklist the provided refresh token to logout the user."""
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    """Verify email using uid and token from verification link."""

    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        """Handle GET to verify a user's email address using uid and token."""
        uid = request.query_params.get("uid")
        token = request.query_params.get("token")
        if not uid or not token:
            return Response(
                {"detail": "Missing uid or token"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            from django.contrib.auth.tokens import default_token_generator
            from django.utils.encoding import force_str
            from django.utils.http import urlsafe_base64_decode

            uid_decoded = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid_decoded)
        except Exception:
            return Response(
                {"detail": "Invalid uid"}, status=status.HTTP_400_BAD_REQUEST
            )
        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            return Response({"detail": "Email verified"})
        return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
