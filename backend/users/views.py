"""API viewsets for user management."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import User
from .serializers import ProfileSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for listing and modifying users."""

    # ОПТИМИЗАЦИЯ: подтягиваем связанный профиль сразу
    queryset = User.objects.select_related('profile').all()
    serializer_class = UserSerializer


class ProfileMeView(APIView):
    """Retrieve or update the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(
            request.user.profile, context={"request": request}
        )
        return Response(serializer.data)

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class UseItemView(APIView):
    """
    Эндпоинт для использования предметов из инвентаря.
    Ожидает POST-запрос с JSON: {"item_type": "hint_scrolls"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        item_type = request.data.get('item_type')
        
        # Проверяем, передали ли название предмета
        if not item_type:
            return Response(
                {"detail": "Не указан тип предмета (item_type)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        profile = request.user.profile
        
        # Используем метод, который мы написали на предыдущем шаге
        success = profile.use_item(item_type)
        
        if success:
            # Получаем актуальный остаток, чтобы фронтенд сразу обновил UI
            remaining = getattr(profile, item_type)
            return Response({
                "detail": "Предмет успешно применен.",
                "item_type": item_type,
                "remaining": remaining
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "detail": "Недостаточно предметов в инвентаре или неверный тип."
            }, status=status.HTTP_400_BAD_REQUEST)
class EmailVerifyView(APIView):
    permission_classes = []

    def get(self, request, token_id):
        token = get_object_or_404(EmailVerificationToken, id=token_id)
        if token.is_used:
            return Response({"detail": "Свиток уже был использован."}, status=status.HTTP_400_BAD_REQUEST)
        
        user = token.user
        user.is_active = True
        user.save()
        
        token.is_used = True
        token.save()
        return Response({"detail": "Магическая печать снята. Аккаунт активирован."})

class ResendVerifyView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get("email")
        # Логика повторной отправки (найти юзера, сгенерировать токен, send_mail)
        return Response({"detail": "Новый почтовый ворон отправлен."})