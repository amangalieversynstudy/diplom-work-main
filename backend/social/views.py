"""HTTP API of the tavern (``/api/social/...``). The rules live in ``social.services``."""

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from game.serializers import _resolve_language

from . import services
from .services import SocialError


class IsPlayer(BasePermission):
    message = "Таверна открыта игрокам. У преподавателя здесь режим просмотра."

    def has_permission(self, request, view):
        return services.is_player(request.user)


class TavernView(APIView):
    """Common base: players only, the layer can be off, rule errors become ``{"detail", "code"}``.

    Every change also passes a scoped throttle (``social_write``) on top of the default per-user one.
    """

    permission_classes = [IsAuthenticated, IsPlayer]
    throttle_scope = "social_write"

    def initial(self, request, *args, **kwargs):
        if not getattr(settings, "SOCIAL_ENABLED", True):
            raise NotFound("Таверна отключена на этом сервере.")
        super().initial(request, *args, **kwargs)

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method not in SAFE_METHODS:
            throttles.append(ScopedRateThrottle())
        return throttles

    def handle_exception(self, exc):
        if isinstance(exc, SocialError):
            return Response({"detail": exc.detail, "code": exc.code}, status=exc.status)
        return super().handle_exception(exc)

    @staticmethod
    def target(request, field="username"):
        player = services.find_player(request.data.get(field))
        if player is None:
            raise SocialError("Игрок с таким логином не найден.", "player_not_found", status.HTTP_404_NOT_FOUND)
        return player

    @staticmethod
    def other(user_id):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.filter(pk=user_id).select_related("profile").first()
        if other is None:
            raise SocialError("Игрок не найден.", "player_not_found", status.HTTP_404_NOT_FOUND)
        return other


class StatusView(TavernView):
    def get(self, request):
        return Response(services.tavern_status(request.user))


class FriendsView(TavernView):
    def get(self, request):
        return Response(services.friends_overview(request.user))

    def post(self, request):
        result = services.request_friend(request.user, self.target(request))
        code = status.HTTP_201_CREATED if result == "pending" else status.HTTP_200_OK
        return Response({"status": result, **services.friends_overview(request.user)}, status=code)


class FriendAcceptView(TavernView):
    def post(self, request, user_id):
        services.accept_friend(request.user, self.other(user_id))
        return Response(services.friends_overview(request.user))


class FriendDetailView(TavernView):
    def delete(self, request, user_id):
        services.remove_friend(request.user, self.other(user_id))
        return Response(services.friends_overview(request.user))


class TradesView(TavernView):
    def get(self, request):
        return Response(services.trades_overview(request.user))

    def post(self, request):
        data = request.data
        services.create_trade(
            request.user,
            self.target(request, "to"),
            data.get("give_item"),
            data.get("give_qty"),
            data.get("ask_item") or None,
            data.get("ask_qty") or 0,
        )
        return Response(services.trades_overview(request.user), status=status.HTTP_201_CREATED)


class TradeActionView(TavernView):
    def post(self, request, pk, action):
        if action == "accept":
            services.accept_trade(request.user, pk)
        elif action in ("decline", "cancel"):
            services.close_trade(request.user, pk, action)
        else:
            raise NotFound()
        request.user.profile.refresh_from_db()
        return Response(services.trades_overview(request.user))


class GuildsView(TavernView):
    def get(self, request):
        return Response(services.guilds_overview(request.user))

    def post(self, request):
        data = request.data
        guild = services.create_guild(request.user, data.get("name"), data.get("motto") or "", data.get("emblem"))
        return Response(services.guild_detail(guild.pk, request.user), status=status.HTTP_201_CREATED)


class GuildDetailView(TavernView):
    def get(self, request, pk):
        return Response(services.guild_detail(pk, request.user))


class GuildJoinView(TavernView):
    def post(self, request, pk):
        services.join_guild(request.user, pk)
        return Response(services.guild_detail(pk, request.user))


class GuildLeaveView(TavernView):
    def post(self, request):
        services.leave_guild(request.user)
        return Response(services.guilds_overview(request.user))


class GuildKickView(TavernView):
    def post(self, request, pk):
        try:
            user_id = int(request.data.get("user_id"))
        except (TypeError, ValueError):
            raise SocialError("Не указан участник.", "bad_member")
        services.kick_member(request.user, pk, user_id)
        return Response(services.guild_detail(pk, request.user))


class DuelsView(TavernView):
    def get(self, request):
        return Response(services.duels_overview(request.user))

    def post(self, request):
        duel = services.create_duel(request.user, self.target(request))
        return Response(services.duel_payload(duel, request.user), status=status.HTTP_201_CREATED)


class DuelStartView(TavernView):
    def post(self, request, pk):
        return Response(services.start_duel(request.user, pk, _resolve_language(request)))


class DuelSubmitView(TavernView):
    def post(self, request, pk):
        return Response(services.submit_duel(request.user, pk, request.data.get("answers")))


class DuelActionView(TavernView):
    def post(self, request, pk, action):
        if action not in ("decline", "cancel"):
            raise NotFound()
        return Response(services.close_duel(request.user, pk, action))
