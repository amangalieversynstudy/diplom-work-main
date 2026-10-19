"""Achievement catalog and evaluation.

The catalog is defined in code (not the DB). Each entry exposes a
``progress(user) -> (current, target)`` callable; an achievement is earned once
``current >= target``. Only unlocks are persisted, via
:class:`game.models.UserAchievement`.

Slugs are stable identifiers. Titles/descriptions are localized on the frontend
(``dictionaries/*.js`` under ``achievements.items.<slug>``). ``icon`` names map
to lucide-react icons the profile page knows how to render.

Most conditions read data that already flows today (missions completed, level,
track completion). ``streak_7`` reads ``Profile.longest_streak``. Level and streak
move with every solved step, so unlocks are evaluated when a step is solved, when a
mission is completed and when the profile list is built.
"""

from django.db.models import Count

from .classes import paying_tracks_q

from .models import Mission, Progress, UserAchievement


def _missions_completed(user):
    # only work that pays globally: an own course or a class of an unvetted teacher gives no badges
    return Progress.objects.filter(user=user, completed=True).filter(
        paying_tracks_q(user, "mission__location__track")
    ).count()


def _tracks_completed(user):
    """Count tracks the user has fully cleared.

    Guards against the fail-open ``Track.is_completed_by`` (an empty track reads
    as "complete"): only tracks with at least one active mission are counted, so
    a misconfigured empty track can't hand out a free achievement.

    Two bounded queries over the learner's own rows, not a loop over every track on the platform: anyone with
    the teacher role can create courses, and this runs on every solved step. ``Count("mission_id")`` is exact
    because Progress is unique per (user, mission).
    """
    done = {
        row["mission__location__track"]: row["n"]
        for row in Progress.objects.filter(
            user=user, completed=True, mission__is_active=True, mission__location__track__isnull=False
        )
        .filter(paying_tracks_q(user, "mission__location__track"))
        .values("mission__location__track")
        .annotate(n=Count("mission_id"))
        .order_by()
    }
    if not done:
        return 0
    totals = (
        Mission.objects.filter(is_active=True, location__track__in=list(done))
        .values("location__track")
        .annotate(n=Count("id"))
        .order_by()
    )
    return sum(1 for row in totals if row["n"] > 0 and done.get(row["location__track"]) == row["n"])


def _level(user):
    return getattr(getattr(user, "profile", None), "level", 1) or 1


def _longest_streak(user):
    return getattr(getattr(user, "profile", None), "longest_streak", 0) or 0


# Order here is the display order on the profile page.
ACHIEVEMENTS = [
    {
        "slug": "first_mission",
        "icon": "Footprints",
        "metric": _missions_completed,
        "target": 1,
    },
    {
        "slug": "five_missions",
        "icon": "Swords",
        "metric": _missions_completed,
        "target": 5,
    },
    {
        "slug": "ten_missions",
        "icon": "Crown",
        "metric": _missions_completed,
        "target": 10,
    },
    {
        "slug": "track_complete",
        "icon": "Flag",
        "metric": _tracks_completed,
        "target": 1,
    },
    {
        "slug": "level_5",
        "icon": "Star",
        "metric": _level,
        "target": 5,
    },
    {
        "slug": "streak_7",
        "icon": "Flame",
        "metric": _longest_streak,
        "target": 7,
    },
]


def _progress(ach, user, measured):
    """(current, target) of one badge; each underlying count runs once per call (``measured`` is the memo)."""
    metric = ach["metric"]
    if metric not in measured:
        measured[metric] = metric(user)
    return measured[metric], ach["target"]


def evaluate_achievements(user):
    """Persist any newly-earned achievements for ``user``; return their slugs.

    Idempotent: already-earned slugs are skipped, and the unique constraint on
    :class:`UserAchievement` makes a concurrent double-call harmless. Safe to
    call from any code path (mission complete, signals, admin actions).
    """
    if getattr(user, "can_teach", False):
        return []  # teachers are not players
    earned = set(
        UserAchievement.objects.filter(user=user).values_list("slug", flat=True)
    )
    newly = []
    measured = {}
    for ach in ACHIEVEMENTS:
        if ach["slug"] in earned:
            continue
        current, target = _progress(ach, user, measured)
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
    evaluate_achievements(user)  # a full progress bar never sits next to a locked badge
    earned = {
        ua.slug: ua.earned_at
        for ua in UserAchievement.objects.filter(user=user)
    }
    items = []
    measured = {}
    for ach in ACHIEVEMENTS:
        current, target = _progress(ach, user, measured)
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
