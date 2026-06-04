"""Authentication views for register, login, logout and email verification."""

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Token views are imported where needed; keep imports local in views that use them
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers_auth import RegisterSerializer, UserDetailSerializer

User = get_user_model()


def _send_verification_email(user):
    """Send the account-activation email with a uid+token link.

    Reused by :class:`RegisterView` (on signup) and
    :class:`ResendVerificationView` (when the user requests a fresh link).
    No-op when the user has no email. Raises on send failure so callers can
    decide whether to swallow the error.
    """
    if not user.email:
        return
    import os

    from django.conf import settings
    from django.contrib.auth.tokens import default_token_generator
    from django.core.mail import send_mail
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    frontend_url = (
        getattr(settings, "FRONTEND_URL", None)
        or os.environ.get("FRONTEND_URL")
        or "http://localhost:3000"
    )
    verify_link = f"{frontend_url.rstrip('/')}/verify-email?uid={uid}&token={token}"
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


# MID-02: rate-limiting декоратор для брутфорс-защиты
# 10 попыток/мин с одного IP — для login и register
@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class LoginView(TokenObtainPairView):
    """Custom login that accepts either username or email."""

    def post(self, request, *args, **kwargs):
        """
        Accept username OR email in the 'username' or 'email' field.

        Frontend sends both fields with the same identifier value:
        - 'username': "smoketest" or "smoke@test.com"
        - 'email': "smoke@test.com" or identifier

        We resolve this to the actual username for authentication.
        """
        # Get identifier from either username or email field
        identifier = request.data.get('username') or request.data.get('email', '')

        if not identifier:
            return Response(
                {"detail": "Укажите username или email"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try to find user by username or email
        user = User.objects.filter(username__iexact=identifier).first()
        if not user:
            user = User.objects.filter(email__iexact=identifier).first()

        # If user found, replace identifier with actual username in request
        if user:
            from django.http import QueryDict
            # Create mutable copy of request data
            if isinstance(request.data, QueryDict):
                mutable_data = request.data.copy()
                mutable_data['username'] = user.username
                request._full_data = mutable_data
            else:
                request.data['username'] = user.username

        # If not found, let TokenObtainPairView handle the error (will return 401)
        return super().post(request, *args, **kwargs)


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post")
class RegisterView(generics.CreateAPIView):
    """Endpoint to register new users and send verification email."""

    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        """Create the user and attempt to send a verification email."""
        from django.conf import settings

        user = serializer.save()
        # Авто-активация если DEBUG=True ИЛИ email backend = console
        # (т.е. реальные письма не уходят, верификация невозможна).
        email_backend = getattr(settings, "EMAIL_BACKEND", "")
        is_console_email = "console" in email_backend
        # Активируем сразу, если: DEBUG, console-backend ИЛИ пользователь не указал email.
        # Без почты верификация невозможна — иначе аккаунт остался бы заблокирован навсегда.
        if getattr(settings, "DEBUG", False) or is_console_email or not user.email:
            user.is_active = True
        else:
            user.is_active = False
        user.save(update_fields=["is_active"])

        # send verification email (console backend in dev)
        try:
            _send_verification_email(user)
        except Exception as e:
            # don't fail registration if email backend misconfigured, but log it
            import logging
            logging.error("[REGISTER] Email send failed for %s: %r", user.email, e)

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


@method_decorator(
    ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post"
)
class ResendVerificationView(APIView):
    """Re-send the activation email for an inactive account.

    Always returns the same generic response regardless of whether the email
    exists or is already active — this avoids leaking which addresses are
    registered. Uses the same uid+token flow as :class:`VerifyEmailView`.
    """

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        """Issue a fresh activation link if the email maps to an inactive user."""
        email = (request.data.get("email") or "").strip()
        generic = Response(
            {
                "detail": (
                    "Если аккаунт существует и ещё не активирован, "
                    "мы отправили новое письмо."
                )
            }
        )
        if not email:
            return generic
        user = User.objects.filter(email__iexact=email).first()
        if user and not user.is_active:
            try:
                _send_verification_email(user)
            except Exception as e:
                import logging
                logging.error("[RESEND] Email send failed for %s: %r", email, e)
        return generic
