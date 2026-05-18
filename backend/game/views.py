"""API viewsets for game models with CodeCombat-like logic."""

from django.db import transaction
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from users.models import Profile
from rest_framework.views import APIView

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

    # ОПТИМИЗАЦИЯ: prefetch_related вытягивает все локации трека заранее
    queryset = Track.objects.prefetch_related('worlds').order_by("order", "id")
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

    # ОПТИМИЗАЦИЯ: select_related для трека (ForeignKey), prefetch_related для миссий (Reverse FK)
    queryset = Location.objects.select_related('track').prefetch_related('missions').order_by("order")
    serializer_class = LocationSerializer
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class MissionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing missions."""

    # ОПТИМИЗАЦИЯ: Вытягиваем локацию миссии и её требования одним запросом
    queryset = Mission.objects.select_related('location').prefetch_related('prerequisites').order_by("order")
    serializer_class = MissionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_permissions(self):
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
            "повтор — процент (repeat_xp_rate).\n"
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

        base_reward = mission.xp_reward
        xp_gain = 0
        if prog.completed and not mission.repeatable:
            xp_gain = 0
        elif prog.completed and mission.repeatable:
            xp_gain = max(0, (base_reward * mission.repeat_xp_rate) // 100)
        else:
            xp_gain = base_reward

        prog.complete()
        prog.xp_earned += xp_gain
        stars = int(request.data.get("stars", 0))
        prog.stars = max(0, min(3, stars))
        prog.save()

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

    @swagger_auto_schema(
        method="post",
        operation_summary="Force complete mission (Admin)",
        operation_description="Завершает миссию за указанного пользователя (обход проверок).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "user_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID пользователя"),
            },
            required=["user_id"],
        ),
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    @transaction.atomic
    def force_complete(self, request, pk=None):
        mission = self.get_object()
        user_id = request.data.get("user_id")
        
        if not user_id:
            return Response({"detail": "user_id is required"}, status=400)
            
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
            
        prog, _ = Progress.objects.get_or_create(user=target_user, mission=mission)
        
        if not prog.completed:
            prog.complete()
            prog.xp_earned += mission.xp_reward
            prog.save()
            target_user.profile.add_xp(mission.xp_reward)
            return Response({"detail": f"Completed for {target_user.username}", "xp_added": mission.xp_reward})
            
        return Response({"detail": "Already completed"}, status=400)


class ProgressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user progress on missions."""

    permission_classes = [permissions.IsAuthenticated]
    queryset = Progress.objects.all()
    serializer_class = ProgressSerializer

    def get_queryset(self):
        return Progress.objects.filter(user=self.request.user).select_related("mission")


class MissionTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose mission tasks/steps for Story → Quiz → Code UX."""

    # Тут уже отлично сделана оптимизация:
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
        # Отличная оптимизация:
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
    # Тут тоже всё было сделано шикарно:
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

class CodeRunnerView(APIView):
    """
    API для безопасного запуска пользовательского кода в песочнице.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Execute Python Code",
        operation_description="Запускает Python-код в изолированном Docker-контейнере.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "code": openapi.Schema(type=openapi.TYPE_STRING, description="Python code to run"),
            },
            required=["code"],
        )
    )
    def post(self, request, *args, **kwargs):
        code = request.data.get("code", "")
        if not code:
            return Response({"status": "error", "output": "Код не предоставлен."}, status=400)
        
        from .runner import execute_python_code
        result = execute_python_code(code)
        
        if result["status"] == "error":
            return Response(result, status=400)
            
        return Response(result, status=200)