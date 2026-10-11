"""Staff-only endpoints for the learning-effectiveness dashboard."""

import csv

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .authorship import authorship_overview, authorship_report
from .live import live_panel
from .me import my_learning
from .metrics import CSV_COLUMNS, clamp_inactive_days, compute_metrics
from .models import UsabilityResponse
from .serializers import _resolve_language
from .throttles import UsabilitySubmitThrottle
from .usability import ITEMS, sus_score
from .warning import early_warning, scoped_learners

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _track_param(request):
    """The optional ``track`` filter as an int, or None when absent/invalid."""
    raw = request.query_params.get("track")
    return int(raw) if raw and raw.isdigit() else None


def _safe_cell(value):
    """Neutralise spreadsheet formulas in text that teachers typed."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return "" if value is None else value


class MyLearningView(APIView):
    """The signed-in learner's own progress, hard spots and next step.

    GET /api/me/learning/

    Only the caller's data, plus one cohort average that is hidden while the
    group is too small to avoid pointing at individuals.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="My learning progress",
        operation_description=(
            "Личный экран ученика: прогресс, где было трудно, что повторить, "
            "следующий шаг и активность за две недели. Без вероятностей риска."
        ),
    )
    def get(self, request):
        return Response(my_learning(request.user, lang=_resolve_language(request)))


class TeacherStudentLearningView(APIView):
    """One student's progress, hard spots and next step, for their teacher.

    GET /api/teacher/students/<id>/learning/

    The same picture the student sees on "My journey", limited to the teacher's
    own courses. A student who does not take the teacher's courses is a 404.
    """

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="A student's learning picture (teacher)",
        operation_description=(
            "Прогресс ученика, где ему трудно, что повторить и следующий шаг. "
            "Только по курсам преподавателя; чужой ученик даёт 404."
        ),
    )
    def get(self, request, pk):
        student = get_object_or_404(scoped_learners(request.user).select_related("profile"), pk=pk)
        owner = None if request.user.is_superuser else request.user
        data = my_learning(student, lang=_resolve_language(request), owner=owner)
        data["student"] = {
            "id": student.pk,
            "username": student.username,
            "level": student.profile.level,
            "xp": student.profile.xp,
        }
        return Response(data)


class TeacherStudentAuthorshipView(APIView):
    """Who solved each code step of one student: alone, with the platform's help, or with signs of outside help.

    GET /api/teacher/students/<id>/authorship/

    The platform's own help (potions, skeleton, mentor) is exact; the editor signals
    (pasting, typing speed) are hints for a conversation, not evidence. Limited to the
    teacher's courses like the learning view.
    """

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Authorship of a student's solved code steps (teacher)",
        operation_description=(
            "По каждому решённому кодовому шагу: самостоятельно, с подсказкой, "
            "со скелетом или с Мудрецом, и признаки внешней помощи по данным "
            "редактора. Признаки не доказательство. Только курсы преподавателя."
        ),
    )
    def get(self, request, pk):
        student = get_object_or_404(scoped_learners(request.user), pk=pk)
        return Response(authorship_report(student, request.user, lang=_resolve_language(request)))


class TeacherAuthorshipOverviewView(APIView):
    """Learners of the teacher's courses whose solutions are worth a conversation, most first.

    GET /api/teacher/authorship/ -> {"students": [{id, username, flagged, solved}]}
    """

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Whose solutions to look at first (teacher)",
        operation_description=(
            "Ученики преподавателя, у которых есть кодовые шаги с признаками внешней помощи. "
            "Это подсказка, с кого начать разговор, а не вывод о списывании."
        ),
    )
    def get(self, request):
        return Response({"students": authorship_overview(request.user)})


class TeacherLiveView(APIView):
    """What the viewer's learners are doing right now, and how stale the previous answer was.

    GET /api/teacher/live/?since=<generated_at of the previous answer>

    The panel calls it every few seconds. ``since`` lets the server measure the data freshness: the
    learner actions that appeared after it are timed (see game/live.py). Without ``since`` nothing is measured.
    """

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Live activity of the teacher's learners",
        operation_description=(
            "Сколько учеников работают сейчас, лента последних действий и задержка данных. "
            "Только ученики и курсы преподавателя; в ленте нет кода учеников."
        ),
    )
    def get(self, request):
        since = parse_datetime(request.query_params.get("since", "") or "")
        if since is not None and since.tzinfo is None:
            since = None
        return Response(live_panel(request.user, lang=_resolve_language(request), since=since))


class TeacherUsabilityView(APIView):
    """The teacher's own System Usability Scale answers about the dashboard.

    GET  /api/teacher/usability/ -> {"answered_at": iso | null}
    POST /api/teacher/usability/ {"answers": [ten ratings 1-5], "comment": "..."} -> {"saved": true}

    A teacher never sees anyone else's answers or the score; the pilot report aggregates them.
    """

    permission_classes = [permissions.IsAdminUser]

    def get_throttles(self):
        # only the submission is limited, reading "did I answer" is not
        if self.request.method == "POST":
            return [UsabilitySubmitThrottle()]
        return super().get_throttles()

    @swagger_auto_schema(operation_summary="Did I already rate the dashboard (teacher)")
    def get(self, request):
        last = UsabilityResponse.objects.filter(user=request.user).first()
        return Response({"answered_at": last.created_at.isoformat() if last else None})

    @swagger_auto_schema(
        operation_summary="Rate the dashboard's usability (teacher)",
        operation_description=f"Десять оценок 1-5 по шкале SUS (system usability scale) и необязательный комментарий. Нужно ровно {ITEMS} оценок.",
    )
    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({"detail": "Ожидается объект."}, status=400)
        try:
            score = sus_score(request.data.get("answers"))
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        comment = str(request.data.get("comment") or "").strip()[:1000]
        # Every answer is kept: the pilot asks for one in the first week and one in the
        # last (docs/PILOT.md); the summary reads the latest. The throttle caps spam.
        UsabilityResponse.objects.create(
            user=request.user, answers=list(request.data["answers"]), score=score, comment=comment
        )
        return Response({"saved": True}, status=201)


class LearningMetricsView(APIView):
    """Mission Completion Rate, Mean Attempts to Success, Task Drop-out Rate.

    GET /api/analytics/metrics/?track=<id>&inactive_days=<n>

    A teacher sees the metrics of their own courses only; a superuser sees all.
    """

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Learning-effectiveness metrics (staff)",
        operation_description=(
            "KPI обучения: доля завершённых миссий, среднее число попыток до "
            "успеха, доля отсева по шагам, порог неудач подряд и эффект "
            "подсказок. Преподаватель видит только свои курсы."
        ),
    )
    def get(self, request):
        return Response(
            compute_metrics(
                request.user,
                track_id=_track_param(request),
                inactive_days=clamp_inactive_days(
                    request.query_params.get("inactive_days")
                ),
            )
        )


class LearningMetricsExportView(APIView):
    """The per-step metrics table as CSV, for a spreadsheet or a thesis chapter."""

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Per-step metrics as CSV (staff)",
        auto_schema=None,
    )
    def get(self, request):
        data = compute_metrics(
            request.user,
            track_id=_track_param(request),
            inactive_days=clamp_inactive_days(request.query_params.get("inactive_days")),
        )
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="learning_metrics.csv"'
        response.write("﻿")  # BOM: Excel opens Cyrillic titles correctly
        writer = csv.writer(response)
        writer.writerow(CSV_COLUMNS)
        for row in data["tasks"]:
            writer.writerow([_safe_cell(row[column]) for column in CSV_COLUMNS])
        return response


class EarlyWarningView(APIView):
    """Learners who need a teacher's attention, with the reasons.

    GET /api/analytics/early-warning/ -> {students, summary, rules}
    """

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(
        operation_summary="Early warning list (staff)",
        operation_description=(
            "Ученики, которым нужна помощь прямо сейчас: несколько неудач "
            "подряд на шаге или долгое молчание при незаконченной работе. "
            "Преподаватель видит только учеников своих курсов."
        ),
    )
    def get(self, request):
        return Response(early_warning(request.user))
