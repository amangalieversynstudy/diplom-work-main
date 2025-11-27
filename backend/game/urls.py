"""URL routes for game API viewsets."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
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
]
