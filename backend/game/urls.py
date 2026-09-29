"""URL routes for game API viewsets."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .analytics_views import (
    EarlyWarningView,
    LearningMetricsExportView,
    LearningMetricsView,
)
from .studio import (
    StudioLocationViewSet,
    StudioMissionViewSet,
    StudioTaskViewSet,
    StudioTrackViewSet,
)
from .views import (
    AchievementsView,
    AIAssistView,
    AIMentorView,
    AnalyticsView,
    CodeRunnerView,
    IntroStatusView,
    LeaderboardViewSet,
    LearningEventView,
    LocationViewSet,
    MissionTaskViewSet,
    MissionViewSet,
    ProgressViewSet,
    RankViewSet,
    TaskProgressViewSet,
    TeacherStudentsView,
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

# Teacher Studio — owner-scoped content authoring (see game/studio.py).
router.register(r"teacher/studio/tracks", StudioTrackViewSet, basename="studio-track")
router.register(
    r"teacher/studio/locations", StudioLocationViewSet, basename="studio-location"
)
router.register(
    r"teacher/studio/missions", StudioMissionViewSet, basename="studio-mission"
)
router.register(r"teacher/studio/tasks", StudioTaskViewSet, basename="studio-task")


urlpatterns = [
    path("", include(router.urls)),
    path("runner/execute/", CodeRunnerView.as_view(), name="runner_execute"),
    path("intro-status/", IntroStatusView.as_view(), name="intro_status"),
    path("ai-assist/", AIAssistView.as_view(), name="ai_assist"),
    path("ai-mentor/", AIMentorView.as_view(), name="ai_mentor"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),
    path(
        "analytics/metrics/",
        LearningMetricsView.as_view(),
        name="learning_metrics",
    ),
    path(
        "analytics/early-warning/",
        EarlyWarningView.as_view(),
        name="early_warning",
    ),
    path(
        "analytics/metrics/export/",
        LearningMetricsExportView.as_view(),
        name="learning_metrics_export",
    ),
    path("achievements/", AchievementsView.as_view(), name="achievements"),
    path("events/", LearningEventView.as_view(), name="learning_events"),
    path(
        "teacher/students/",
        TeacherStudentsView.as_view(),
        name="teacher_students",
    ),
]
