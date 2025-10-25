from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Token views are imported where needed; keep imports local in views that use them
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers_auth import RegisterSerializer, UserDetailSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        # send verification email (console backend in dev)
        try:
            from django.contrib.auth.tokens import default_token_generator
            from django.core.mail import send_mail
            from django.utils.encoding import force_bytes
            from django.utils.http import urlsafe_base64_encode

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            verify_link = f"/api/auth/verify-email/?uid={uid}&token={token}"
            send_mail("Verify your email", f"Click: {verify_link}", None, [user.email])
        except Exception:
            pass


class MeView(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserDetailSerializer

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    """Blacklist refresh token to logout a user."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
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
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
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
