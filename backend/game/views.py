"""API viewsets for game models with CodeCombat-like logic."""

import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Max, Q, Sum, Value, When
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status, viewsets
from rest_framework.throttling import UserRateThrottle
from rest_framework.decorators import action
from rest_framework.response import Response
from users.models import Profile
from rest_framework.views import APIView

from .achievements import evaluate_achievements
from .footprint import find_task, log_event, log_help_offer
from .services import (
    RuleViolation,
    check_mission_access,
    check_task_order,
    grade_quiz,
    mission_stars,
    only_live_missions,
    only_published,
    progress_payload,
    record_task_attempt,
    require_mission_tasks_done,
)
from .throttles import (
    AIAssistThrottle,
    CodeRunnerBurstThrottle,
    CodeRunnerThrottle,
    LearningEventThrottle,
    MissionCompleteThrottle,
    TaskSubmitThrottle,
    TeacherAnalyticsThrottle,
)

logger = logging.getLogger(__name__)

MAX_LANGUAGE_LENGTH = 32


def _valid_language(value):
    """The programming language name sent to Gemini: a short string, nothing else."""
    return isinstance(value, str) and len(value) <= MAX_LANGUAGE_LENGTH

# Что видит ученик, когда AI недоступен. Причину (нет ключа, сбой сети) не показываем:
# она нужна администратору, а не первокурснику, и попадает в журнал сервера.
AI_UNAVAILABLE = (
    "🔮 Мудрец сейчас недоступен, и твой вызов не потрачен. "
    "Попробуй Зелье Ясности или вернись чуть позже."
)

from .models import (
    LearningEvent,
    LeaderboardEntry,
    Location,
    Mission,
    MissionTask,
    Progress,
    Rank,
    TaskProgress,
    Track,
)
from .classes import MISSION_TRACK, member_or_public, owner_scope, pays_globally, visible_learners, visible_work
from .permissions import IsSuperUser, IsTeacher
from .variants import personalize
from .metrics import _last_activity, student_performance_map
from .warning import assess_students
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
            # drafts stay hidden; closed courses (classes) only for their owner and the learners who joined
            return only_published(qs, self.request.user, "").filter(is_active=True)
        return qs

    def get_permissions(self):
        # Reads are public; writes are superuser-only. Teachers author their
        # own courses via the owner-scoped Studio API (game/studio.py), so the
        # public endpoint never lets one teacher edit another's content.
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [IsSuperUser()]


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing locations."""

    # ОПТИМИЗАЦИЯ: select_related для трека (ForeignKey), prefetch_related для миссий (Reverse FK)
    queryset = Location.objects.select_related('track').prefetch_related('missions').order_by("order")
    serializer_class = LocationSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return only_published(super().get_queryset(), self.request.user, "track")

    def get_permissions(self):
        # Reads public; writes superuser-only (teachers use the Studio API).
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [IsSuperUser()]


class MissionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing missions."""

    # ОПТИМИЗАЦИЯ: Вытягиваем локацию миссии и её требования одним запросом
    # Порядок «курс → локация → миссия»: без него миссии двух курсов с одинаковыми
    # order перемешиваются, и тропа на карте прыгает между курсами.
    queryset = (
        Mission.objects.select_related('location', 'location__track', 'location__track__owner')
        .prefetch_related('prerequisites')
        .order_by("location__track__order", "location__order", "order", "id")
    )
    serializer_class = MissionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = only_published(
            super().get_queryset(), self.request.user, "location__track"
        )
        # a draft is shown to the course owner and vetted staff only
        return only_live_missions(qs, self.request.user)

    def get_permissions(self):
        if self.action in ("start", "complete"):
            return [permissions.IsAuthenticated()]
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        # Writes superuser-only (teachers use the Studio API).
        return [IsSuperUser()]

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
        check_mission_access(request.user, mission)

        prog, _ = Progress.objects.get_or_create(user=request.user, mission=mission)
        prog.start()
        log_event(
            request.user,
            LearningEvent.MISSION_STARTED,
            mission=mission,
            attempt=prog.attempts,
        )
        return Response(ProgressSerializer(prog).data)

    @swagger_auto_schema(
        method="post",
        operation_summary="Complete mission",
        operation_description=(
            "Завершает миссию и начисляет XP: первый раз — полный reward, "
            "повтор — процент (repeat_xp_rate). Требует, чтобы все обязательные "
            "задачи миссии были засчитаны сервером. Звёзды считает сервер."
        ),
        responses={200: ProgressSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        throttle_classes=[UserRateThrottle, MissionCompleteThrottle],
    )
    @transaction.atomic
    def complete(self, request, pk=None):
        mission = self.get_object()
        user = request.user
        check_mission_access(user, mission)

        prog, _ = Progress.objects.get_or_create(user=user, mission=mission)
        # Lock the progress and profile rows: two parallel completions must not
        # both see "not completed yet" and both award the XP.
        prog = Progress.objects.select_for_update().get(pk=prog.pk)
        profile: Profile = user.profile
        Profile.objects.select_for_update().get(pk=profile.pk)
        profile.refresh_from_db()

        # A finished mission that cannot be repeated is answered with its state and no side effects: no save
        # (which would rebuild the leaderboard), no event, no achievements. The same for a double click within 5 s.
        if (prog.completed and not mission.repeatable) or (
            prog.completed
            and prog.completed_at
            and timezone.now() - prog.completed_at < timedelta(seconds=5)
        ):
            return Response(
                {**self._completion_payload(prog, profile, 0, False, deduplicated=True), "preview": bool(user.can_teach)}
            )

        awards_xp = (not prog.completed) or mission.repeatable
        if awards_xp:
            require_mission_tasks_done(user, mission)

        was_completed = prog.completed
        xp_gain = 0
        if not prog.completed:
            xp_gain = mission.xp_reward
        elif mission.repeatable:
            xp_gain = max(0, (mission.xp_reward * mission.repeat_xp_rate) // 100)
        if user.can_teach:
            xp_gain = 0  # a teacher's trial run is graded but pays nothing
        # class XP of a class whose XP stays inside it: Progress.xp_earned only (see classes.pays_globally)
        global_pay = pays_globally(user, mission.location.track if mission.location_id else None)

        # XP first: the leaderboard signal fired by saving the progress below
        # reads the profile, so it must already contain the new XP.
        leveled_up = False
        if xp_gain > 0 and global_pay:
            leveled_up, _old, _new = profile.add_xp(xp_gain)

        prog.xp_earned += xp_gain
        if awards_xp:
            prog.stars = max(prog.stars, mission_stars(user, mission))
        if prog.completed:
            prog.save()
        else:
            prog.complete()

        log_event(
            user,
            LearningEvent.MISSION_COMPLETED,
            mission=mission,
            xp_added=xp_gain,
            stars=prog.stars,
            first_time=not was_completed,
        )
        # complete() also updated the streak on another Profile instance.
        profile.refresh_from_db()
        new_achievements = evaluate_achievements(user) if global_pay else []
        payload = self._completion_payload(
            prog,
            profile,
            xp_gain,
            leveled_up,
            new_achievements=new_achievements,
            first_completion=not was_completed,
        )
        payload["counts_globally"] = global_pay
        payload["preview"] = bool(user.can_teach)
        return Response(payload)

    @staticmethod
    def _completion_payload(
        prog,
        profile,
        xp_added,
        leveled_up,
        new_achievements=None,
        deduplicated=False,
        first_completion=False,
    ):
        data = ProgressSerializer(prog).data
        data.update(
            {
                "xp_added": xp_added,
                # true only for the first completion: then ``xp_earned`` is what the mission paid in total
                "first_completion": first_completion,
                "leveled_up": leveled_up,  # triggers the level-up burst on the client
                "new_level": profile.level,
                "profile_level": profile.level,
                "profile_xp": profile.xp,
                "ai_summons": profile.ai_summons,
                "hint_scrolls": profile.hint_scrolls,
                "skeleton_scrolls": profile.skeleton_scrolls,
                # slugs of achievements unlocked just now (the client shows a toast)
                "new_achievements": new_achievements or [],
            }
        )
        if deduplicated:
            data["deduplicated"] = True
        return data


class ProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """A learner's own mission progress (read-only: the server writes it)."""

    permission_classes = [permissions.IsAuthenticated]
    queryset = Progress.objects.all()
    serializer_class = ProgressSerializer

    def get_queryset(self):
        return Progress.objects.filter(user=self.request.user).select_related("mission")


class MissionTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """Mission tasks/steps for Story → Quiz → Code UX.

    The answer key never leaves the server (see services.public_task_data);
    story and quiz steps are answered through ``submit``, code steps by running
    the code through the WebSocket runner with the task id.
    """

    queryset = MissionTask.objects.select_related(
        "mission", "mission__location", "mission__location__track__owner"
    ).order_by(
        "mission_id", "order"
    )
    serializer_class = MissionTaskSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = only_published(
            super().get_queryset(), self.request.user, "mission__location__track"
        )
        qs = only_live_missions(qs, self.request.user, "mission")
        mission_id = self.request.query_params.get("mission")
        if mission_id:
            qs = qs.filter(mission_id=mission_id) if mission_id.isdigit() else qs.none()
        task_type = self.request.query_params.get("task_type")
        if task_type:
            qs = qs.filter(task_type=task_type)
        return qs

    @swagger_auto_schema(
        method="post",
        operation_summary="Submit a story or quiz step",
        operation_description=(
            "Story: засчитывается сразу. Quiz: тело {\"answer\": \"...\"}, ответ "
            "проверяет сервер. Код проверяется при запуске в раннере."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"answer": openapi.Schema(type=openapi.TYPE_STRING)},
            required=[],
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        throttle_classes=[TaskSubmitThrottle],
    )
    def submit(self, request, pk=None):
        task = self.get_object()
        user = request.user
        check_mission_access(user, task.mission)
        check_task_order(user, task)

        if task.task_type == "story":
            passed, answer = True, {}
        elif task.task_type == "quiz":
            given = request.data.get("answer")
            if (
                isinstance(given, bool)
                or not isinstance(given, (str, int, float))
                or str(given).strip() == ""
            ):
                raise RuleViolation("answer is required", status.HTTP_400_BAD_REQUEST)
            # graded on the learner's own variant of the question (game/variants.py)
            passed, answer = grade_quiz(personalize(task, user.pk), given), {"selected": given}
        else:
            raise RuleViolation(
                "Code tasks are checked when you run the code",
                status.HTTP_400_BAD_REQUEST,
            )

        task_progress = record_task_attempt(
            user, task, passed=passed, score=100 if passed else 0, answer=answer
        )
        log_event(
            user,
            LearningEvent.TASK_SUBMITTED,
            task=task,
            task_type=task.task_type,
            kind=task.kind,
            correct=passed,
            attempt=task_progress.attempts,
            after_solved=not task_progress.counted,
        )
        payload = progress_payload(task_progress)
        if task_progress.counted and not passed:
            log_help_offer(user, task, payload)
        return Response(
            {
                "correct": passed,
                "completed": task_progress.status == "completed",
                "progress": payload,
            }
        )


class TaskProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """A learner's own progress on mission tasks (read-only).

    Only the server records attempts, scores and completion, so nobody can mark
    a task as solved by posting to this endpoint.
    """

    queryset = TaskProgress.objects.none()
    serializer_class = TaskProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = TaskProgress.objects.filter(user=self.request.user).select_related(
            "task", "task__mission"
        )
        mission_id = self.request.query_params.get("mission")
        if mission_id:
            qs = (
                qs.filter(task__mission_id=mission_id)
                if mission_id.isdigit()
                else qs.none()
            )
        return qs


class RankViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rank.objects.all().order_by("order", "min_level", "min_xp")
    serializer_class = RankSerializer
    permission_classes = [permissions.AllowAny]


class LeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    # Тут тоже всё было сделано шикарно:
    queryset = LeaderboardEntry.objects.select_related(
        "track", "user", "user__profile", "user__profile__class_role"
    )
    serializer_class = LeaderboardEntrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        # Teachers and staff are not players. Rows of a closed class (and who studies there) are for its members
        # and owner only, and a learner who left the class drops out of its table.
        qs = qs.filter(user__is_staff=False, user__is_teacher=False)
        visible_tracks = only_published(Track.objects.all(), self.request.user, "")
        qs = qs.filter(Q(track__isnull=True) | (Q(track__in=visible_tracks) & member_or_public("track")))
        track_slug = self.request.query_params.get("track")
        if track_slug:
            qs = qs.filter(track__slug=track_slug)
        # Every learner has one "global" row and one "track" row per course. Reading both at
        # once listed the same person several times, so one table is read unless asked otherwise.
        scope = self.request.query_params.get("scope") or ("track" if track_slug else "global")
        qs = qs.filter(scope=scope)
        period = self.request.query_params.get("period")
        if period:
            qs = qs.filter(period_label=period)
        else:
            qs = qs.filter(period_label="all_time")
        # XP primary, streak secondary, username tertiary tiebreaker —
        # стабильная сортировка чтобы карточки не прыгали между запросами.
        # Серия, оборванная больше суток назад, показывается нулём (Profile.streak_active),
        # поэтому и в ничьей она не должна выигрывать.
        yesterday = timezone.localdate() - timedelta(days=1)
        qs = qs.annotate(
            live_streak=Case(
                When(
                    user__profile__last_streak_date__gte=yesterday,
                    then=F("user__profile__current_streak"),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        return qs.order_by("-xp_total", "-live_streak", "user__username")

    def list(self, request, *args, **kwargs):
        # the top 200 is cut here and not in get_queryset, so GET /leaderboard/<id>/ can still filter the rows
        rows = self.filter_queryset(self.get_queryset())[:200]
        return Response(self.get_serializer(rows, many=True).data)

class IntroStatusView(APIView):
    """Reports whether the current user has finished the intro course.

    The class page is open to everyone; this status tells the client when to
    *suggest* choosing a class (after the last mission of the "intro" Track, a
    Track with is_intro=True). If no intro track is configured the answer is
    "unlocked" — nobody is held back by a misconfigured server.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Class-selection unlock status",
        operation_description=(
            "Возвращает class_unlocked=True, если пользователь завершил "
            "вводный трек (или если такой трек не настроен)."
        ),
    )
    def get(self, request):
        intro = Track.get_intro()
        if intro is None:
            return Response({
                "class_unlocked": True,
                "intro_track": None,
                "progress": None,
                "reason": "no_intro_configured",
            })

        completed = intro.is_completed_by(request.user)
        progress = intro.completion_progress(request.user)
        return Response({
            "class_unlocked": completed,
            "intro_track": {
                "slug": intro.slug,
                "title": intro.get_localized_title("ru"),
                "title_en": intro.get_localized_title("en"),
            },
            "progress": progress,
            "reason": None if completed else "intro_not_completed",
        })


class CodeRunnerView(APIView):
    """
    API для безопасного запуска пользовательского кода в Docker-песочнице.

    Throttling: 20 запусков/мин на юзера + burst 5/10с — защищает контейнер-хост
    от спам-кликов и DDoS.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [CodeRunnerThrottle, CodeRunnerBurstThrottle]

    # Лимит размера присылаемого исходника — защита от мегабайтных payload-ов
    MAX_CODE_LENGTH = 10_000

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
            return Response(
                {"status": "error", "output": "Код не предоставлен."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(code) > self.MAX_CODE_LENGTH:
            return Response(
                {
                    "status": "error",
                    "output": f"Код превышает лимит {self.MAX_CODE_LENGTH} символов.",
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        from .runner import execute_python_code
        from .throttles import acquire_run, release_run

        # один запуск на ученика сразу (общий ключ с WebSocket)
        if not acquire_run(request.user.pk):
            return Response(
                {"status": "error", "output": "Код уже запускается — дождись результата."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            result = execute_python_code(code)
        finally:
            release_run(request.user.pk)

        if result["status"] == "error":
            return Response(result, status=400)

        return Response(result, status=200)


class AIAssistView(APIView):
    """AI-помощник (Gemini) для code-заданий — выдаёт подсказку, не решение.

    POST /api/game/ai-assist/  {code, task_description, language} -> {hint}

    Throttling: 10 запросов/мин на юзера (Gemini-квота дорогая).
    Если GEMINI_API_KEY не задан — возвращает локальный fallback вместо 500.
    Списывает 1 ai_summon из инвентаря пользователя только при УСПЕХЕ.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AIAssistThrottle]

    MAX_CODE_LENGTH = 8_000
    MAX_DESCRIPTION_LENGTH = 4_000

    _SYSTEM_PROMPT = (
        "You are Sage — a wise, concise mentor inside an RPG coding academy. "
        "The student is stuck on a programming task. "
        "Give ONE clear, actionable hint in 2–4 sentences. "
        "Do NOT provide the full solution — guide the student to discover it. "
        "Respond in the same language as the task description (Russian or English). "
        "Keep a slightly mystical, encouraging RPG tone."
    )

    @swagger_auto_schema(
        operation_summary="AI Hint (Gemini)",
        operation_description=(
            "Выдаёт подсказку по задаче. Списывает 1 ai_summons из инвентаря "
            "только при успешном ответе. Лимит — 10/мин на юзера."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "code": openapi.Schema(type=openapi.TYPE_STRING),
                "task_description": openapi.Schema(type=openapi.TYPE_STRING),
                "language": openapi.Schema(type=openapi.TYPE_STRING, default="python"),
            },
            required=["task_description"],
        ),
    )
    def post(self, request):
        code = request.data.get("code") or ""
        task_description = request.data.get("task_description") or ""
        language = request.data.get("language", "python")
        if not isinstance(code, str) or not isinstance(task_description, str) or not _valid_language(language):
            return Response({"detail": "Invalid code, task_description or language"}, status=status.HTTP_400_BAD_REQUEST)
        code, task_description = code.strip(), task_description.strip()

        if not task_description:
            return Response(
                {"detail": "task_description is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(code) > self.MAX_CODE_LENGTH:
            return Response(
                {"detail": f"code превышает лимит {self.MAX_CODE_LENGTH} символов"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        if len(task_description) > self.MAX_DESCRIPTION_LENGTH:
            return Response(
                {
                    "detail": (
                        f"task_description превышает лимит "
                        f"{self.MAX_DESCRIPTION_LENGTH} символов"
                    )
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        profile = request.user.profile
        # Вызов резервируем ДО обращения к AI: иначе параллельные запросы при
        # одном оставшемся вызове получили бы по ответу, а списался бы один.
        if not profile.use_item("ai_summons"):
            return Response(
                {
                    "detail": (
                        "Нет вызовов AI-помощника. Заработай новый уровень — "
                        "получишь больше свитков."
                    ),
                    "remaining_summons": 0,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            hint, ok = self._call_gemini(code, task_description, language)
        except Exception:
            profile.refund_item("ai_summons")
            raise
        if not ok:
            # текст — заглушка «AI недоступен»: расход возвращаем
            profile.refund_item("ai_summons")
        if ok:
            log_event(
                request.user,
                LearningEvent.AI_HINT_USED,
                task=find_task(request.data.get("task_id"), request.user),
            )

        return Response(
            {
                "hint": hint,
                "remaining_summons": profile.ai_summons,
            }
        )

    def _call_gemini(self, code: str, description: str, language: str):
        """Возвращает кортеж (text, success_flag).

        success_flag=False — текст это user-friendly fallback, инвентарь НЕ
        списываем.
        """
        import os

        from django.conf import settings as _settings

        api_key = getattr(_settings, "GEMINI_API_KEY", None) or os.environ.get(
            "GEMINI_API_KEY"
        )

        if not api_key:
            logger.error("GEMINI_API_KEY is not set: the AI mentor is unavailable")
            return (AI_UNAVAILABLE, False)

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.warning("google-genai не установлен — Gemini выключен")
            return (AI_UNAVAILABLE, False)

        try:
            model_name = getattr(_settings, "GEMINI_MODEL", None) or os.environ.get(
                "GEMINI_MODEL", "gemini-2.5-flash"
            )
            client = genai.Client(
                api_key=api_key,
                http_options={"api_version": "v1"},
            )

            task_block = (
                f"Task:\n{description}\n\n"
                f"Language: {language}\n\n"
                f"Student's current code:\n```{language}\n{code}\n```"
            ) if code else f"Task:\n{description}\n\nLanguage: {language}"

            contents = f"{self._SYSTEM_PROMPT}\n\n{task_block}"

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                ),
            )

            # Достаём текст из всех parts кандидата — response.text иногда
            # возвращает только первый part (особенно в gemini-2.5 с thinking).
            text = (response.text or "").strip()
            if not text and getattr(response, "candidates", None):
                parts_text = []
                for cand in response.candidates:
                    for part in getattr(getattr(cand, "content", None), "parts", []) or []:
                        if getattr(part, "text", None):
                            parts_text.append(part.text)
                text = "".join(parts_text).strip()

            # Логируем причину завершения для диагностики обрезанных ответов
            finish_reason = None
            try:
                finish_reason = str(response.candidates[0].finish_reason)
            except (AttributeError, IndexError):
                pass
            logger.info("Gemini finish_reason=%s, text_len=%d", finish_reason, len(text))

            if not text:
                return (
                    "🧙 Наставник задумался... попробуй переформулировать вопрос.",
                    False,
                )
            return text, True
        except Exception:
            logger.exception("Gemini API call failed")
            return (
                "🌫️ Мудрец сейчас в глубокой медитации и не может ответить. "
                "Попробуй спросить чуть позже.",
                False,
            )


def _call_gemini_chat(system_instruction: str, history: list):
    """Многоходовой вызов Gemini для AI-наставника.

    history — список реплик [{"role": "user"|"model", "content": str}].
    Возвращает кортеж (text, success_flag); при success_flag=False text — это
    user-friendly fallback, и ману (ai_summons) списывать НЕ нужно.

    Логика разрешения ключа/модели и устойчивого извлечения текста повторяет
    AIAssistView._call_gemini, но передаёт всю историю диалога и системную
    инструкцию с контекстом задачи и текущего кода ученика.
    """
    import os

    from django.conf import settings as _settings

    api_key = getattr(_settings, "GEMINI_API_KEY", None) or os.environ.get(
        "GEMINI_API_KEY"
    )
    if not api_key:
        logger.error("GEMINI_API_KEY is not set: the AI mentor is unavailable")
        return (AI_UNAVAILABLE, False)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai не установлен — Gemini выключен")
        return (AI_UNAVAILABLE, False)

    try:
        model_name = getattr(_settings, "GEMINI_MODEL", None) or os.environ.get(
            "GEMINI_MODEL", "gemini-2.5-flash"
        )
        client = genai.Client(
            api_key=api_key,
            http_options={"api_version": "v1"},
        )

        # ВАЖНО: v1-эндпоинт generateContent НЕ знает поля systemInstruction
        # (это фича v1beta) — передача system_instruction в конфиге роняет
        # запрос с 400 "Unknown name systemInstruction". Поэтому, как и в
        # рабочем AIAssistView._call_gemini, вплетаем системную инструкцию в
        # текст первой реплики пользователя и остаёмся на проверенном v1.
        contents = []
        injected = False
        for turn in history:
            text = turn["content"]
            if not injected and turn["role"] == "user":
                text = f"{system_instruction}\n\n---\n\n{text}"
                injected = True
            contents.append(
                types.Content(
                    role=turn["role"],
                    parts=[types.Part(text=text)],
                )
            )
        if not injected:
            # пограничный случай: первая реплика не от user — добавим контекст
            # отдельной user-репликой в начало диалога.
            contents.insert(
                0,
                types.Content(
                    role="user",
                    parts=[types.Part(text=system_instruction)],
                ),
            )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=2048,
                temperature=0.7,
            ),
        )

        text = (response.text or "").strip()
        if not text and getattr(response, "candidates", None):
            parts_text = []
            for cand in response.candidates:
                for part in getattr(getattr(cand, "content", None), "parts", []) or []:
                    if getattr(part, "text", None):
                        parts_text.append(part.text)
            text = "".join(parts_text).strip()

        finish_reason = None
        try:
            finish_reason = str(response.candidates[0].finish_reason)
        except (AttributeError, IndexError):
            pass
        logger.info(
            "Gemini(mentor) finish_reason=%s, text_len=%d", finish_reason, len(text)
        )

        if not text:
            return (
                "🧙 Наставник задумался... попробуй переформулировать вопрос.",
                False,
            )
        return text, True
    except Exception:
        logger.exception("Gemini mentor call failed")
        return (
            "🌫️ Мудрец сейчас в глубокой медитации и не может ответить. "
            "Попробуй задать вопрос чуть позже.",
            False,
        )


class AIMentorView(APIView):
    """Контекстный AI-наставник (Sage) — диалог, а не одна подсказка.

    POST /api/game/ai-mentor/
        {messages: [{role, content}], code, task_description, language}
        -> {reply, remaining_summons}

    Backend stateless: история диалога приходит с фронта. Каждый УСПЕШНЫЙ
    ответ Мудреца списывает 1 ai_summon (ману) — та же экономика, что и у
    разового хинта, но теперь это полноценная беседа с памятью о контексте.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AIAssistThrottle]

    MAX_CODE_LENGTH = 8_000
    MAX_DESCRIPTION_LENGTH = 4_000
    MAX_MESSAGE_LENGTH = 2_000
    MAX_HISTORY = 24  # последних реплик хватает, ограничивает токен-расход

    _SYSTEM_PROMPT = (
        "You are Sage — a wise, patient mentor inside an RPG coding academy. "
        "You are in an ongoing conversation with a student who is solving a "
        "programming task. Answer their questions and guide their thinking with "
        "hints, leading questions, concept explanations and bug spotting — but do "
        "NOT hand over a complete, ready-to-paste solution; lead the student to "
        "discover it themselves. Keep replies concise (2–6 sentences) unless the "
        "student explicitly asks you to go deeper. Always reply in the same "
        "language the student writes in (Russian or English). Keep a slightly "
        "mystical, encouraging RPG tone while staying technically accurate."
    )

    @swagger_auto_schema(
        operation_summary="AI Mentor chat (Gemini)",
        operation_description=(
            "Контекстный диалог с AI-наставником. Принимает историю сообщений, "
            "текущий код и описание задачи. Списывает 1 ai_summons за каждый "
            "успешный ответ. Лимит — 10/мин на юзера."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "messages": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "role": openapi.Schema(type=openapi.TYPE_STRING),
                            "content": openapi.Schema(type=openapi.TYPE_STRING),
                        },
                    ),
                ),
                "code": openapi.Schema(type=openapi.TYPE_STRING),
                "task_description": openapi.Schema(type=openapi.TYPE_STRING),
                "language": openapi.Schema(type=openapi.TYPE_STRING, default="python"),
            },
            required=["messages"],
        ),
    )
    def post(self, request):
        raw_messages = request.data.get("messages")
        code = request.data.get("code") or ""
        task_description = request.data.get("task_description") or ""
        language = request.data.get("language", "python")
        if not isinstance(code, str) or not isinstance(task_description, str) or not _valid_language(language):
            return Response({"detail": "Invalid code, task_description or language"}, status=status.HTTP_400_BAD_REQUEST)
        code, task_description = code.strip(), task_description.strip()

        if not isinstance(raw_messages, list) or not raw_messages:
            return Response(
                {"detail": "messages must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Берём только последние MAX_HISTORY реплик и нормализуем роли:
        # фронт шлёт "assistant", Gemini ждёт "model".
        history = []
        for item in raw_messages[-self.MAX_HISTORY :]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content") or ""
            content = content.strip() if isinstance(content, str) else ""
            if not content or role not in ("user", "assistant", "model"):
                continue
            history.append(
                {
                    "role": "user" if role == "user" else "model",
                    "content": content[: self.MAX_MESSAGE_LENGTH],
                }
            )

        if not history or history[-1]["role"] != "user":
            return Response(
                {"detail": "last message must come from the user"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(code) > self.MAX_CODE_LENGTH:
            return Response(
                {"detail": f"code превышает лимит {self.MAX_CODE_LENGTH} символов"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        if len(task_description) > self.MAX_DESCRIPTION_LENGTH:
            return Response(
                {
                    "detail": (
                        f"task_description превышает лимит "
                        f"{self.MAX_DESCRIPTION_LENGTH} символов"
                    )
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        profile = request.user.profile
        # Резервируем вызов до обращения к AI (см. AIAssistView).
        if not profile.use_item("ai_summons"):
            return Response(
                {
                    "detail": (
                        "Мана иссякла — нет вызовов Мудреца. Заверши уровень, "
                        "чтобы пополнить запас свитков."
                    ),
                    "remaining_summons": 0,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        # Системная инструкция = персона + контекст задачи + текущий код ученика.
        system_instruction = self._SYSTEM_PROMPT
        if task_description:
            system_instruction += f"\n\n# Current task\n{task_description}"
        system_instruction += f"\n\n# Language\n{language}"
        if code:
            system_instruction += (
                f"\n\n# Student's current code\n```{language}\n{code}\n```"
            )

        try:
            reply, ok = _call_gemini_chat(system_instruction, history)
        except Exception:
            profile.refund_item("ai_summons")
            raise
        if not ok:
            profile.refund_item("ai_summons")
        if ok:
            log_event(
                request.user,
                LearningEvent.AI_MENTOR_USED,
                task=find_task(request.data.get("task_id"), request.user),
            )

        return Response(
            {
                "reply": reply,
                "remaining_summons": profile.ai_summons,
            }
        )


class AchievementsView(APIView):
    """The signed-in user's achievement catalog with earned status + progress.

    GET /api/achievements/ -> [{slug, icon, target, current, earned, earned_at}]

    The catalog lives in :mod:`game.achievements` (code, not DB); this endpoint
    just annotates each entry with the caller's progress. Titles/descriptions
    are localized on the frontend by slug.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .achievements import achievements_for

        return Response(achievements_for(request.user))


class TeacherStudentsView(APIView):
    """Сводка по всем ученикам для кабинета преподавателя (staff-only).

    Отвечает на вопрос «кому нужна помощь прямо сейчас?»: по каждому ученику —
    уровень/XP, сколько миссий завершено и сколько в работе, как давно он был
    активен, и флаг «застрял» (с причиной), чтобы преподаватель видел узкие
    места без ручного разбора прогресса.

    GET /api/teacher/students/ -> {students: [...], summary: {...}}
    """

    permission_classes = [IsTeacher]

    def get_throttles(self):
        # тяжёлый пересчёт на каждый запрос: свой лимит поверх общего
        return [*super().get_throttles(), TeacherAnalyticsThrottle()]

    @swagger_auto_schema(
        operation_summary="Teacher cabinet: per-student progress (staff)",
        operation_description=(
            "Список учеников (не-staff) с уровнем/XP, числом завершённых и "
            "взятых в работу миссий, последней активностью и флагом «застрял». "
            "Доступно только staff."
        ),
    )
    def get(self, request):
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        User = get_user_model()

        # Преподаватель видит только «своих» учеников — тех, кто проходит миссии
        # его курсов (Студия). Суперюзер видит всех. Используем подзапрос id__in
        # (а не JOIN-фильтр), чтобы агрегаты ниже остались точными.
        base = visible_learners(request.user)
        viewer = request.user
        owner = owner_scope(viewer)

        # Счётчики миссий и XP отдельным запросом по Progress: только курсы преподавателя, а закрытый курс только
        # пока ученик в классе (для суперпользователя фильтр пустой). Progress уникален по (ученик, миссия),
        # поэтому distinct не нужен и суммы не двоятся.
        counts = {
            row["user_id"]: row
            for row in Progress.objects.filter(user__in=base)
            .filter(visible_work(viewer, MISSION_TRACK))
            .values("user_id")
            .annotate(
                done=Count("id", filter=Q(completed=True)),
                open=Count("id", filter=Q(completed=False, status="in_progress")),
                xp=Sum("xp_earned"),
            )
            .order_by()
        }
        rows = base.select_related("profile")
        if owner is None:
            rows = list(rows.order_by("-profile__xp", "username"))
        else:
            # преподаватель видит XP своих курсов, по нему и сортировка (глобальный XP не раскрывается)
            rows = sorted(rows, key=lambda s: (-(counts.get(s.id, {}).get("xp") or 0), s.username))

        # «Застрял» решает система раннего предупреждения (game/warning.py):
        # несколько неудач подряд на шаге либо долгое молчание при незаконченной
        # работе. Попытки миссии (Progress.attempts) для этого не годятся: это
        # число стартов, а не ошибок.
        warnings = assess_students(request.user, now=now)
        # «Активность» считается так же, как в списке раннего предупреждения: любые события, запуски кода,
        # попытки и старты/завершения миссий, а не только старт и завершение миссии.
        activity = _last_activity([s.id for s in rows], owner=owner)
        from .patterns import student_behavioral_patterns_map

        perf_by_user = student_performance_map(viewer, [s.id for s in rows])
        patterns_by_user = student_behavioral_patterns_map(viewer, [s.id for s in rows])
        students = []
        stuck_count = 0
        active_week = 0
        for s in rows:
            profile = getattr(s, "profile", None)
            last_active = activity.get(s.id)
            warning = warnings.get(s.id)
            codes = {r["code"] for r in warning["reasons"]} if warning else set()
            stuck = bool(warning) and warning["level"] != "ok"
            stuck_reason = (
                "many_attempts"
                if stuck and "stuck_task" in codes
                else ("inactive" if stuck and "inactive" in codes else None)
            )
            own = counts.get(s.id, {})
            open_count = own.get("open") or 0
            max_attempts = warning["failures"] if warning else 0

            if stuck:
                stuck_count += 1
            if last_active and last_active >= week_ago:
                active_week += 1

            students.append(
                {
                    "id": s.id,
                    "username": s.username,
                    "display_name": s.display_name or "",
                    # уровень и серия считаются по всей платформе: преподавателю их не показываем
                    "level": getattr(profile, "level", 1) if owner is None else None,
                    "xp": getattr(profile, "xp", 0) if owner is None else (own.get("xp") or 0),
                    "current_streak": getattr(profile, "current_streak", 0) if owner is None else None,
                    "completed_count": own.get("done") or 0,
                    "in_progress_count": open_count,
                    "max_attempts": max_attempts,
                    "last_active": last_active.isoformat() if last_active else None,
                    "stuck": stuck,
                    "stuck_reason": stuck_reason,
                    # the same level as the early-warning list, so both screens speak one language
                    "warning_level": warning["level"] if warning else "ok",
                    "performance_score": (perf_by_user.get(s.id) or {}).get("score"),
                    "behavioral_pattern": (patterns_by_user.get(s.id) or {}).get("code", "insufficient_data"),
                }
            )

        return Response(
            {
                "students": students,
                "summary": {
                    "total_students": len(students),
                    "stuck_count": stuck_count,
                    "active_week": active_week,
                    "mean_performance": (
                        round(
                            sum(s["performance_score"] for s in students if s.get("performance_score") is not None)
                            / sum(1 for s in students if s.get("performance_score") is not None),
                            1,
                        )
                        if any(s.get("performance_score") is not None for s in students)
                        else None
                    ),
                },
            }
        )


class LearningEventView(APIView):
    """Timeline events reported by the browser.

    Only harmless UI events are accepted here (a step was opened). Everything
    with consequences - attempts, hints, completions - is recorded by the
    server itself when it happens, never on the client's word.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [LearningEventThrottle]
    ALLOWED_TYPES = {LearningEvent.TASK_OPENED}

    def post(self, request):
        event_type = request.data.get("event_type")
        if event_type not in self.ALLOWED_TYPES:
            return Response(
                {"detail": "Unsupported event type"}, status=status.HTTP_400_BAD_REQUEST
            )
        task = find_task(request.data.get("task_id"), request.user)
        if task is None:
            return Response(
                {"detail": "Task not found"}, status=status.HTTP_404_NOT_FOUND
            )
        log_event(request.user, event_type, task=task)
        return Response(status=status.HTTP_204_NO_CONTENT)
