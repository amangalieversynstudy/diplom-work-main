"""Signals: keep leaderboard entries fresh when progress changes.

Раньше модель `LeaderboardEntry` существовала, но никто её
не создавал — `/leaderboard/` всегда возвращал пустой список.
Теперь при каждом `Progress.complete()` мы апдейтим entry с
актуальным XP-тоталом и пересчитываем позиции в global-таблице.
"""

from django.db.models import Sum
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

    track = getattr(getattr(instance.mission, "location", None), "track", None)
    refresh_leaderboard(instance.user, track)


def refresh_leaderboard(user, track=None, profile=None):
    """Upsert the learner's global (and course) entries and renumber the places.

    Called when a mission is completed and when a solved step pays XP, so the
    leaderboard never lags behind the XP bar. Teachers are not players. The global row moves only with work
    that pays globally (``classes.pays_globally``); a class keeps its own course row. Places are renumbered only
    when a total actually changed, in one bulk update.
    """
    from .classes import pays_globally

    if getattr(user, "can_teach", False):
        return
    # the caller may hand over the profile it has just changed: ``user.profile`` can be a stale copy
    profile = profile or getattr(user, "profile", None)
    if not profile:
        return

    if track is None or pays_globally(user, track):
        if _upsert(user, "global", None, profile.xp):
            _recalculate_positions(scope="global", track=None, period_label="all_time")

    if track:
        # XP в рамках одного трека: сумма xp_earned по этому треку
        track_xp = (
            Progress.objects.filter(user=user, mission__location__track=track).aggregate(s=Sum("xp_earned"))["s"]
            or 0
        )
        if _upsert(user, "track", track, track_xp):
            _recalculate_positions(scope="track", track=track, period_label="all_time")


def _upsert(user, scope, track, xp_total):
    """Create or update one all_time row; True when the total changed (or the row is new)."""
    entry, created = LeaderboardEntry.objects.get_or_create(
        user=user, scope=scope, track=track, period_label="all_time", defaults={"xp_total": xp_total}
    )
    if created:
        return True
    if entry.xp_total == xp_total:
        return False
    LeaderboardEntry.objects.filter(pk=entry.pk).update(xp_total=xp_total)
    return True


def _recalculate_positions(scope: str, track, period_label: str):
    """Нумерация по убыванию XP одним bulk_update только для строк, чьё место изменилось."""
    rows = list(
        LeaderboardEntry.objects.filter(scope=scope, track=track, period_label=period_label)
        .order_by("-xp_total", "user_id")
        .only("id", "position")
    )
    changed = []
    for idx, entry in enumerate(rows, start=1):
        if entry.position != idx:
            entry.position = idx
            changed.append(entry)
    if changed:
        LeaderboardEntry.objects.bulk_update(changed, ["position"], batch_size=500)
