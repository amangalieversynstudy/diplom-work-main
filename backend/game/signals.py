"""Signals: keep leaderboard entries fresh when progress changes.

HIGH-03: Раньше модель `LeaderboardEntry` существовала, но никто её
не создавал — `/leaderboard/` всегда возвращал пустой список.
Теперь при каждом `Progress.complete()` мы апдейтим entry с
актуальным XP-тоталом и пересчитываем позиции в global-таблице.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LeaderboardEntry, Progress


@receiver(post_save, sender=Progress)
def update_leaderboard_on_progress(sender, instance: Progress, created, **kwargs):
    """Apsert global leaderboard entry для юзера + пересчёт позиций."""
    # Сигнал может срабатывать на любой save — нам интересно только
    # когда миссия завершена и есть XP.
    if not instance.completed:
        return

    user = instance.user
    profile = getattr(user, "profile", None)
    if not profile:
        return

    # ── 1. Upsert global all_time entry ──
    LeaderboardEntry.objects.update_or_create(
        user=user,
        scope="global",
        track=None,
        period_label="all_time",
        defaults={"xp_total": profile.xp},
    )

    # ── 2. Upsert track-specific entry, если миссия привязана к треку ──
    track = getattr(getattr(instance.mission, "location", None), "track", None)
    if track:
        # XP в рамках одного трека: сумма xp_earned по этому треку
        track_xp = (
            Progress.objects
            .filter(user=user, mission__location__track=track, completed=True)
            .values_list("xp_earned", flat=True)
        )
        LeaderboardEntry.objects.update_or_create(
            user=user,
            scope="track",
            track=track,
            period_label="all_time",
            defaults={"xp_total": sum(track_xp)},
        )

    # ── 3. Пересчёт позиций (rank) в global all_time ──
    _recalculate_positions(scope="global", track=None, period_label="all_time")
    if track:
        _recalculate_positions(scope="track", track=track, period_label="all_time")


def _recalculate_positions(scope: str, track, period_label: str):
    """Простая нумерация по убыванию XP. Для production — заменить на
    оконные функции SQL (ROW_NUMBER OVER ORDER BY xp_total DESC) или
    Celery-job, если пользователей много."""
    qs = LeaderboardEntry.objects.filter(
        scope=scope, track=track, period_label=period_label
    ).order_by("-xp_total", "user_id")
    for idx, entry in enumerate(qs, start=1):
        if entry.position != idx:
            entry.position = idx
            entry.save(update_fields=["position"])
