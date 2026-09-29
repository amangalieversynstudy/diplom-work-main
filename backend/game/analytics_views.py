"""Staff-only endpoints for the learning-effectiveness dashboard."""

import csv

from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .metrics import CSV_COLUMNS, clamp_inactive_days, compute_metrics

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
