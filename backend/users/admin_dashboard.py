"""Cheap live counters for the admin dashboard (counts only)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone


def dashboard_stats():
    from game.models import CodeRun, Mission, Track

    User = get_user_model()
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        ("Учеников", User.objects.filter(is_teacher=False, is_staff=False).count()),
        ("Преподавателей", User.objects.filter(is_teacher=True).count()),
        ("Курсов", Track.objects.count()),
        ("Классов", Track.objects.filter(owner__isnull=False).count()),
        ("Опубликованных миссий", Mission.objects.filter(is_active=True).count()),
        ("Запусков кода сегодня", CodeRun.objects.filter(created_at__gte=today).count()),
        ("Новых за 7 дней", User.objects.filter(date_joined__gte=now - timedelta(days=7)).count()),
    ]
