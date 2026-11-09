from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.StatusView.as_view(), name="social_status"),
    path("friends/", views.FriendsView.as_view(), name="social_friends"),
    path("friends/<int:user_id>/accept/", views.FriendAcceptView.as_view(), name="social_friend_accept"),
    path("friends/<int:user_id>/", views.FriendDetailView.as_view(), name="social_friend"),
    path("trades/", views.TradesView.as_view(), name="social_trades"),
    path("trades/<int:pk>/<str:action>/", views.TradeActionView.as_view(), name="social_trade_action"),
    path("guilds/", views.GuildsView.as_view(), name="social_guilds"),
    path("guilds/leave/", views.GuildLeaveView.as_view(), name="social_guild_leave"),
    path("guilds/<int:pk>/", views.GuildDetailView.as_view(), name="social_guild"),
    path("guilds/<int:pk>/join/", views.GuildJoinView.as_view(), name="social_guild_join"),
    path("guilds/<int:pk>/kick/", views.GuildKickView.as_view(), name="social_guild_kick"),
    path("duels/", views.DuelsView.as_view(), name="social_duels"),
    path("duels/<int:pk>/start/", views.DuelStartView.as_view(), name="social_duel_start"),
    path("duels/<int:pk>/submit/", views.DuelSubmitView.as_view(), name="social_duel_submit"),
    path("duels/<int:pk>/<str:action>/", views.DuelActionView.as_view(), name="social_duel_action"),
]
