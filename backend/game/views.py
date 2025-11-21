"""API viewsets for game models with CodeCombat-like logic."""

from django.db import transaction
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from users.models import Profile

from .models import (
    LeaderboardEntry,
    Location,
    Mission,
    MissionTask,
    Progress,
    Rank,
    TaskProgress,
    Track,
)
from .serializers import (
    LeaderboardEntrySerializer,
    LocationSerializer,
    MissionSerializer,
    MissionTaskSerializer,
    ProgressSerializer,
    RankSerializer,
    TaskProgressSerializer,
    TrackSerializer,
)


class TrackViewSet(viewsets.ModelViewSet):
    """ViewSet for learning tracks."""

    queryset = Track.objects.all().order_by("order", "id")
    serializer_class = TrackSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing locations."""

    queryset = Location.objects.all().order_by("order")
    serializer_class = LocationSerializer
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        # Read-only for all; write operations for admins only
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class MissionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing missions."""

    queryset = Mission.objects.all().order_by("order")
    serializer_class = MissionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        # Read-only for all; write operations for admins only
        # (except custom actions below)
        if self.action in ("start", "complete"):
            return [permissions.IsAuthenticated()]
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @swagger_auto_schema(
        method="post",
        operation_summary="Start mission",
        operation_description=(
            "Начинает попытку прохождения миссии. Проверяет is_active, "
            "min_level, prerequisites.\n"
            "Инкрементирует attempts, выставляет статус in_progress."
        ),
        responses={200: ProgressSerializer},
    )
    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    @transaction.atomic
    def start(self, request, pk=None):
        mission = self.get_object()
        profile: Profile = request.user.profile

        # availability checks like CodeCombat doors
        if not mission.is_active:
            return Response({"detail": "Mission is inactive"}, status=400)
        if profile.level < mission.min_level:
            return Response({"detail": "Level too low"}, status=403)
        if mission.prerequisites.exists():
            completed_ids = set(
                Progress.objects.filter(user=request.user, completed=True).values_list(
                    "mission_id", flat=True
                )
            )
            missing = [
                m.id for m in mission.prerequisites.all() if m.id not in completed_ids
            ]
            if missing:
                return Response({"detail": "Prerequisites not completed"}, status=403)

        prog, _ = Progress.objects.get_or_create(user=request.user, mission=mission)
        prog.start()
        return Response(ProgressSerializer(prog).data)

    @swagger_auto_schema(
        method="post",
        operation_summary="Complete mission",
        operation_description=(
            "Завершает миссию и начисляет XP: первый раз — полный reward, "
            "повтор — процент (repeat_xp_rate),\n"
            "если миссия не repeatable — повтор без XP. "
            "Можно передать 'stars' (0..3)."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "stars": openapi.Schema(type=openapi.TYPE_INTEGER, description="0..3"),
            },
            required=[],
        ),
        responses={200: ProgressSerializer},
    )
    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    @transaction.atomic
    def complete(self, request, pk=None):
        mission = self.get_object()
        profile: Profile = request.user.profile
        # Повторяем проверки доступности как при старте
        if not mission.is_active:
            return Response({"detail": "Mission is inactive"}, status=400)
        if profile.level < mission.min_level:
            return Response({"detail": "Level too low"}, status=403)
        if mission.prerequisites.exists():
            completed_ids = set(
                Progress.objects.filter(user=request.user, completed=True).values_list(
                    "mission_id", flat=True
                )
            )
            missing = [
                m.id for m in mission.prerequisites.all() if m.id not in completed_ids
            ]
            if missing:
                return Response({"detail": "Prerequisites not completed"}, status=403)

        prog, _ = Progress.objects.get_or_create(user=request.user, mission=mission)

        # if already completed and not repeatable -> no XP
        base_reward = mission.xp_reward
        xp_gain = 0
        if prog.completed and not mission.repeatable:
            xp_gain = 0
        elif prog.completed and mission.repeatable:
            # repeat XP rate (percentage of base)
            xp_gain = max(0, (base_reward * mission.repeat_xp_rate) // 100)
        else:
            xp_gain = base_reward

        # apply complete
        prog.complete()
        prog.xp_earned += xp_gain
        # optional: compute stars based on extra criteria (placeholder 0-3)
        stars = int(request.data.get("stars", 0))
        prog.stars = max(0, min(3, stars))
        prog.save()

        # add XP to profile
        if xp_gain > 0:
            profile.add_xp(xp_gain)

        data = ProgressSerializer(prog).data
        data.update(
            {
                "xp_added": xp_gain,
                "profile_xp": profile.xp,
                "profile_level": profile.level,
            }
        )
        return Response(data)


class ProgressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user progress on missions."""

    permission_classes = [permissions.IsAuthenticated]
    queryset = Progress.objects.all()
    serializer_class = ProgressSerializer

    def get_queryset(self):
        # Users can only access their own progress
        return Progress.objects.filter(user=self.request.user).select_related("mission")


class MissionTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose mission tasks/steps for Story → Quiz → Code UX."""

    queryset = MissionTask.objects.select_related("mission", "mission__location").order_by(
        "mission_id", "order"
    )
    serializer_class = MissionTaskSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        mission_id = self.request.query_params.get("mission")
        if mission_id:
            qs = qs.filter(mission_id=mission_id)
        task_type = self.request.query_params.get("task_type")
        if task_type:
            qs = qs.filter(task_type=task_type)
        return qs


class TaskProgressViewSet(viewsets.ModelViewSet):
    """Allow learners to persist their progress on mission tasks."""

    queryset = TaskProgress.objects.none()
    serializer_class = TaskProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TaskProgress.objects.filter(user=self.request.user).select_related(
            "task", "task__mission"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class RankViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rank.objects.all().order_by("order", "min_level", "min_xp")
    serializer_class = RankSerializer
    permission_classes = [permissions.AllowAny]


class LeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaderboardEntry.objects.select_related("track", "user", "user__profile")
    serializer_class = LeaderboardEntrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        track_slug = self.request.query_params.get("track")
        if track_slug:
            qs = qs.filter(track__slug=track_slug)
        scope = self.request.query_params.get("scope")
        if scope:
            qs = qs.filter(scope=scope)
        period = self.request.query_params.get("period")
        if period:
            qs = qs.filter(period_label=period)
        else:
            qs = qs.filter(period_label="all_time")
        return qs.order_by("position", "-xp_total")[:200]
