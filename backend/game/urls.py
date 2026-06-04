"""URL routes for game API viewsets."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AIAssistView,
    AIMentorView,
    AnalyticsView,
    CodeRunnerView,
    IntroStatusView,
    LeaderboardViewSet,
    LocationViewSet,
    MissionTaskViewSet,
    MissionViewSet,
    ProgressViewSet,
    RankViewSet,
    TaskProgressViewSet,
    TrackViewSet,
)

router = DefaultRouter()
router.register(r"locations", LocationViewSet)
router.register(r"missions", MissionViewSet)
router.register(r"progress", ProgressViewSet)
router.register(r"tracks", TrackViewSet)
router.register(r"mission-tasks", MissionTaskViewSet)
router.register(r"task-progress", TaskProgressViewSet, basename="task-progress")
router.register(r"ranks", RankViewSet)
router.register(r"leaderboard", LeaderboardViewSet, basename="leaderboard")


urlpatterns = [
    path("", include(router.urls)),
    path("runner/execute/", CodeRunnerView.as_view(), name="runner_execute"),
    path("intro-status/", IntroStatusView.as_view(), name="intro_status"),
    path("ai-assist/", AIAssistView.as_view(), name="ai_assist"),
    path("ai-mentor/", AIMentorView.as_view(), name="ai_mentor"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),
]
