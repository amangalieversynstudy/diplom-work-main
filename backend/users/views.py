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
    """Retrieve or update the authenticated user's profile.

    Returns a flat object that combines User (username/email/display_name)
    and Profile (xp/level/inventory/class_role) — the frontend expects this shape.
    PATCH accepts any subset of these fields.
    """

    permission_classes = [IsAuthenticated]

    def _payload(self, user):
        profile = user.profile
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            # staff видит аналитику/кабинет преподавателя (гейтинг на фронте)
            "is_staff": user.is_staff,
            "xp": profile.xp,
            "level": profile.level,
            "bio": profile.bio,
            "class_role": profile.class_role_id,
            "ai_summons": profile.ai_summons,
            "hint_scrolls": profile.hint_scrolls,
            "skeleton_scrolls": profile.skeleton_scrolls,
            # HIGH-01: ранг пользователя для отображения в профиле
            "rank": profile.current_rank,
        }

    def get(self, request):
        return Response(self._payload(request.user))

    def patch(self, request):
        user = request.user
        profile = user.profile
        data = request.data or {}

        # User-поля: username / email / display_name
        user_dirty = []
        if "username" in data and data["username"]:
            new_username = str(data["username"]).strip()
            if new_username != user.username:
                # check uniqueness
                if User.objects.exclude(pk=user.pk).filter(username=new_username).exists():
                    return Response(
                        {"username": "Такое имя пользователя уже занято."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.username = new_username
                user_dirty.append("username")
        if "email" in data and data["email"] is not None:
            new_email = str(data["email"]).strip().lower()
            if new_email != (user.email or "").lower():
                if new_email and User.objects.exclude(pk=user.pk).filter(email__iexact=new_email).exists():
                    return Response(
                        {"email": "Этот email уже используется."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.email = new_email
                user_dirty.append("email")
        if "display_name" in data:
            user.display_name = str(data["display_name"] or "")
            user_dirty.append("display_name")
        if user_dirty:
            user.save(update_fields=user_dirty)

        # Profile-поля — через сериализатор (нужна валидация class_role)
        profile_payload = {k: data[k] for k in ("bio", "class_role") if k in data}
        if profile_payload:
            serializer = ProfileSerializer(
                profile, data=profile_payload, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response(self._payload(user))

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