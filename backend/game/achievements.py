"""Achievement catalog and evaluation.

The catalog is defined in code (not the DB). Each entry exposes a
``progress(user) -> (current, target)`` callable; an achievement is earned once
``current >= target``. Only unlocks are persisted, via
:class:`game.models.UserAchievement`.

Slugs are stable identifiers. Titles/descriptions are localized on the frontend
(``dictionaries/*.js`` under ``achievements.items.<slug>``). ``icon`` names map
to lucide-react icons the profile page knows how to render.

Most conditions read data that already flows today (missions completed, level,
track completion). ``streak_7`` reads ``Profile.longest_streak`` and will light
up once streak tracking lands (roadmap item: visible streak).
"""

from .models import Mission, Progress, Track, UserAchievement


def _missions_completed(user):
    return Progress.objects.filter(user=user, completed=True).count()


def _tracks_completed(user):
    """Count tracks the user has fully cleared.

    Guards against the fail-open ``Track.is_completed_by`` (an empty track reads
    as "complete"): only tracks with at least one active mission are counted, so
    a misconfigured empty track can't hand out a free achievement.
    """
    count = 0
    for track in Track.objects.all():
        total = Mission.objects.filter(
            location__track=track, is_active=True
        ).count()
        if total > 0 and track.is_completed_by(user):
            count += 1
    return count


def _level(user):
    return getattr(getattr(user, "profile", None), "level", 1) or 1


def _longest_streak(user):
    return getattr(getattr(user, "profile", None), "longest_streak", 0) or 0


# Order here is the display order on the profile page.
ACHIEVEMENTS = [
    {
        "slug": "first_mission",
        "icon": "Footprints",
        "progress": lambda u: (_missions_completed(u), 1),
    },
    {
        "slug": "five_missions",
        "icon": "Swords",
        "progress": lambda u: (_missions_completed(u), 5),
    },
    {
        "slug": "ten_missions",
        "icon": "Crown",
        "progress": lambda u: (_missions_completed(u), 10),
    },
    {
        "slug": "track_complete",
        "icon": "Flag",
        "progress": lambda u: (_tracks_completed(u), 1),
    },
    {
        "slug": "level_5",
        "icon": "Star",
        "progress": lambda u: (_level(u), 5),
    },
    {
        "slug": "streak_7",
        "icon": "Flame",
        "progress": lambda u: (_longest_streak(u), 7),
    },
]


def evaluate_achievements(user):
    """Persist any newly-earned achievements for ``user``; return their slugs.

    Idempotent: already-earned slugs are skipped, and the unique constraint on
    :class:`UserAchievement` makes a concurrent double-call harmless. Safe to
    call from any code path (mission complete, signals, admin actions).
    """
    earned = set(
        UserAchievement.objects.filter(user=user).values_list("slug", flat=True)
    )
    newly = []
    for ach in ACHIEVEMENTS:
        if ach["slug"] in earned:
            continue
        current, target = ach["progress"](user)
        if current >= target:
            _, created = UserAchievement.objects.get_or_create(
                user=user, slug=ach["slug"]
            )
            if created:
                newly.append(ach["slug"])
    return newly


def achievements_for(user):
    """Return the full catalog annotated with this user's status and progress.

    Shape (list of dicts) is what ``GET /api/achievements/`` and the profile
    page consume. ``current`` is clamped to ``target`` so progress bars never
    overflow.
    """
    earned = {
        ua.slug: ua.earned_at
        for ua in UserAchievement.objects.filter(user=user)
    }
    items = []
    for ach in ACHIEVEMENTS:
        current, target = ach["progress"](user)
        items.append(
            {
                "slug": ach["slug"],
                "icon": ach["icon"],
                "target": int(target),
                "current": min(int(current), int(target)),
                "earned": ach["slug"] in earned,
                "earned_at": earned.get(ach["slug"]),
            }
        )
    return items
