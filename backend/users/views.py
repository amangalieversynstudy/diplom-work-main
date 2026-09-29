"""API viewsets for user management."""

from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import User
from .serializers import ProfileSerializer
from .validators import clean_single_email, clean_username

# A confirmation e-mail goes to an address the user typed, so how often one may
# be sent is capped: the platform's sender domain must not become a mail relay.
EMAIL_CHANGE_LIMIT = 5
EMAIL_CHANGE_WINDOW = 60 * 60


def _email_change_allowed(user):
    """Count this attempt; False once the hourly allowance is used up."""
    key = f"email-change:{user.pk}"
    cache.add(key, 0, EMAIL_CHANGE_WINDOW)
    try:
        return cache.incr(key) <= EMAIL_CHANGE_LIMIT
    except ValueError:  # the key expired between add and incr
        cache.set(key, 1, EMAIL_CHANGE_WINDOW)
        return True


def _parse_bool(value):
    """True/False for JSON booleans and 'true'/'false' strings, else None."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None

# NOTE: there is intentionally no generic /api/users/ endpoint. Users are only
# ever read/changed through their own /profile/me/ (see ProfileMeView), and
# user management goes through the Django admin.


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
            # ранг пользователя для отображения в профиле
            "rank": profile.current_rank,
            # Стрик: счётчики + флаги для видимого стрика и напоминания.
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "streak_active": profile.streak_active,
            "streak_at_risk": profile.streak_at_risk,
            # согласие на использование активности в исследовании
            "research_consent": profile.research_consent,
            "research_consent_at": profile.research_consent_at,
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
                try:
                    new_username = clean_username(new_username, exclude_pk=user.pk)
                except DjangoValidationError as error:
                    return Response(
                        {"username": " ".join(error.messages)},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.username = new_username
                user_dirty.append("username")
        email_change_pending = None
        if "email" in data and data["email"] is not None:
            new_email = str(data["email"]).strip().lower()
            if new_email != (user.email or "").lower():
                if new_email:
                    try:
                        new_email = clean_single_email(new_email)
                    except DjangoValidationError as error:
                        return Response(
                            {"email": " ".join(error.messages)},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if not _email_change_allowed(user):
                        return Response(
                            {"email": "Слишком много попыток смены email. Попробуйте позже."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS,
                        )
                    # Смена/добавление email требует подтверждения владения новым
                    # ящиком. НЕ пишем user.email сразу — старый адрес остаётся
                    # активным, пока юзер не кликнет по ссылке. Так опечатка в
                    # адресе не лочит аккаунт.
                    if User.objects.exclude(pk=user.pk).filter(email__iexact=new_email).exists():
                        return Response(
                            {"email": "Этот email уже используется."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    from .views_auth import _send_email_change_email
                    try:
                        _send_email_change_email(user, new_email)
                        email_change_pending = new_email
                    except Exception as e:
                        import logging
                        logging.error(
                            "[EMAIL-CHANGE] send failed for %s: %r", new_email, e
                        )
                        return Response(
                            {"email": "Не удалось отправить письмо подтверждения. Попробуйте позже."},
                            status=status.HTTP_502_BAD_GATEWAY,
                        )
                else:
                    # Удаление email — без подтверждения (это не захват ящика).
                    user.email = ""
                    user_dirty.append("email")
        if "display_name" in data:
            user.display_name = str(data["display_name"] or "")
            user_dirty.append("display_name")
        if user_dirty:
            user.save(update_fields=user_dirty)

        if "research_consent" in data:
            consent = _parse_bool(data["research_consent"])
            if consent is None:
                return Response(
                    {"research_consent": "Ожидается true или false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile.set_research_consent(consent)
            profile.save(update_fields=["research_consent", "research_consent_at"])

        # Profile-поля — через сериализатор (нужна валидация class_role)
        profile_payload = {k: data[k] for k in ("bio", "class_role") if k in data}
        if profile_payload:
            serializer = ProfileSerializer(
                profile, data=profile_payload, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        payload = self._payload(user)
        if email_change_pending:
            # Фронт показывает баннер «подтверждение отправлено на <email>».
            payload["email_change_pending"] = email_change_pending
        return Response(payload)

# inventory item -> timeline event (ai_summons is logged by the AI views)
ITEM_EVENTS = {"hint_scrolls": "hint_used", "skeleton_scrolls": "skeleton_used"}


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
            event_type = ITEM_EVENTS.get(item_type)
            if event_type:
                from game.footprint import find_task, log_event

                log_event(
                    request.user,
                    event_type,
                    task=find_task(request.data.get("task_id"), request.user),
                )
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