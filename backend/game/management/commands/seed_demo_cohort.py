"""A made-up class for a demonstration, so the teacher's screens are not empty.

    python manage.py seed_demo_cohort --teacher teacher1          # 24 demo learners
    python manage.py seed_demo_cohort --teacher teacher1 --count 40
    python manage.py seed_demo_cohort --remove                    # take them all away

Demo learners are the users whose name starts with ``demo_``. Each one plays one of a few recognisable
ways: steady, helped by the platform, pasting solutions, sharing a solution with a friend, stuck on a step,
gone for weeks. Everything the teacher's screens read is filled in: progress, attempts, runs with editor
counts, hints, the explain question, XP and the leaderboard. They never take part in the research export
(no consent). The command removes the previous demo cohort first, so running it twice leaves one class.

Do not leave them in a database that real learners use: ``pilot_check`` warns while they exist.
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.models import CodeRun, LearningEvent, Mission, MissionTask, Progress, TaskProgress, Track
from game.signals import refresh_leaderboard
from game.variants import variant_index, variants_of

DEMO_PREFIX = "demo_"
# archetype -> (missions played, share of the class in tenths)
ARCHETYPES = (
    ("steady", 3, 4),
    ("helped", 3, 2),
    ("paster", 3, 1),
    ("twin", 2, 1),
    ("stuck", 2, 1),
    ("away", 2, 1),
)
ERRORS = ("NameError", "SyntaxError", "TypeError", "IndentationError", "NameError")
TWIN_NODES = 60


def demo_users():
    return get_user_model().objects.filter(username__startswith=DEMO_PREFIX)


def _typed(length, rng):
    return {"typed_chars": length, "pasted_chars": 0, "paste_count": 0, "edit_events": length,
            "edits_after_paste": 0, "elapsed_ms": rng.randint(90, 420) * 1000}


def _pasted(length, rng):
    return {"typed_chars": rng.randint(0, 12), "pasted_chars": length, "paste_count": 1, "edit_events": 2,
            "edits_after_paste": rng.randint(0, 1), "elapsed_ms": rng.randint(4, 14) * 1000}


class Command(BaseCommand):
    help = "Create (or remove) a demo class with a recognisable footprint for the teacher's screens."

    def add_arguments(self, parser):
        parser.add_argument("--teacher", help="Username of the teacher who owns the courses to play.")
        parser.add_argument("--count", type=int, default=24, help="Number of demo learners (default 24).")
        parser.add_argument("--remove", action="store_true", help="Only remove the demo learners.")
        parser.add_argument("--seed", type=int, default=7, help="Random seed (same seed, same class).")

    def handle(self, *args, **options):
        removed = demo_users().delete()[0]
        if options["remove"]:
            self.stdout.write(self.style.SUCCESS(f"removed demo rows: {removed}"))
            return
        count = options["count"]
        if not 4 <= count <= 200:
            raise CommandError("--count must be between 4 and 200.")

        tracks = Track.objects.filter(is_active=True)
        if options["teacher"]:
            tracks = tracks.filter(owner__username=options["teacher"])
        if not tracks.exists():
            raise CommandError(
                "No course to play: pass --teacher with a teacher who owns a course "
                "(see set_course_owner), or seed the courses first (seed_course)."
            )
        missions = list(
            Mission.objects.filter(location__track__in=tracks, is_active=True, tasks__isnull=False)
            .distinct()
            .select_related("location", "location__track")
            .order_by("location__track__order", "location__order", "order", "id")
        )
        steps = [
            list(MissionTask.objects.filter(mission=mission).order_by("order", "id")) for mission in missions
        ]
        if len(steps) < 3:
            raise CommandError("The courses need at least three missions to play a demo class.")

        rng = random.Random(options["seed"])
        roster = []
        for name, _, tenths in ARCHETYPES:
            roster += [name] * max(1, round(count * tenths / 10))
        roster = (roster + ["steady"] * count)[:count]
        rng.shuffle(roster)

        now = timezone.now()
        User = get_user_model()
        twins = []
        for index, archetype in enumerate(roster, start=1):
            user = User.objects.create_user(f"{DEMO_PREFIX}{index:02d}", password=None)  # no one can log in
            if archetype == "twin":
                twins.append(user)
            self._play(user, archetype, steps, now, rng, twin_of=twins[-2] if archetype == "twin" and len(twins) % 2 == 0 else None)
        self.stdout.write(self.style.SUCCESS(f"demo learners: {count} ({removed} old rows removed)"))

    # ── one learner ────────────────────────────────────────────────────────

    def _play(self, user, archetype, steps, now, rng, twin_of=None):
        missions_to_play = dict((name, played) for name, played, _ in ARCHETYPES)[archetype]
        last = now - timedelta(days=rng.randint(18, 35) if archetype == "away" else rng.randint(0, 2))
        xp = 0
        stopped = False
        track = None
        for mission_steps in steps[:missions_to_play]:
            mission = mission_steps[0].mission
            track = mission.location.track
            mission_xp = 0
            for task in mission_steps:
                solved_xp = self._play_step(user, archetype, task, last, rng, twin_of)
                if solved_xp is None:  # stuck here
                    stopped = True
                    break
                mission_xp += solved_xp
            done = not stopped
            if done:
                mission_xp += mission.xp_reward
            xp += mission_xp
            Progress.objects.create(
                user=user, mission=mission, completed=done, status="completed" if done else "in_progress",
                started_at=last - timedelta(days=1), last_started_at=last, completed_at=last if done else None,
                xp_earned=mission_xp, stars=3 if done and archetype == "steady" else (2 if done else 0),
            )
            if stopped:
                break

        profile = user.profile
        profile.xp = xp
        profile.level = xp // 100 + 1
        if archetype != "away":
            profile.current_streak = rng.randint(1, 6)
            profile.longest_streak = profile.current_streak + rng.randint(0, 3)
            profile.last_streak_date = now.date()
        profile.save()
        if track is not None:
            refresh_leaderboard(user, track, profile=profile)
        LearningEvent.objects.filter(user=user).update(created_at=last)
        CodeRun.objects.filter(user=user).update(created_at=last)

    def _play_step(self, user, archetype, task, last, rng, twin_of):
        """XP earned by the step, or None when the learner gets stuck on it (and stops)."""
        LearningEvent.objects.create(user=user, event_type="task_opened", task=task)
        explain = task.kind == "explain"
        if task.task_type == "story":
            TaskProgress.objects.create(user=user, task=task, status="completed", attempts=1, last_submitted_at=last)
            return task.xp_reward

        if task.task_type == "quiz":
            fails = rng.choice([0, 0, 1, 2]) if not explain else 0
            if explain and archetype == "paster":
                fails = 3
            elif explain and archetype == "helped":
                fails = rng.choice([0, 1])
            TaskProgress.objects.create(
                user=user, task=task, status="completed", attempts=fails + 1, last_submitted_at=last
            )
            return task.xp_reward

        # a code step
        stuck = archetype == "stuck" and task.order == 3 and task.mission.order >= 1
        fails = rng.randint(4, 6) if stuck else rng.choice([0, 1, 2]) if archetype != "paster" else rng.choice([0, 0, 1])
        if archetype == "helped":
            fails = rng.randint(2, 4)
        for n in range(fails):
            CodeRun.objects.create(
                user=user, task=task, outcome="error", error_type=rng.choice(ERRORS), passed=False, attempt_no=n + 1,
                code_length=rng.randint(30, 120),
            )
        if archetype == "helped":
            for kind in rng.sample(["hint_used", "hint_used", "skeleton_used", "ai_mentor_used"], rng.randint(1, 3)):
                LearningEvent.objects.create(user=user, event_type=kind, task=task)
        if stuck:
            TaskProgress.objects.create(user=user, task=task, status="in_progress", attempts=fails, last_submitted_at=last)
            return None

        length = rng.randint(90, 260)
        provenance = _pasted(length, rng) if archetype == "paster" else _typed(length, rng)
        fingerprint = f"demo{user.pk:05d}{task.pk:05d}"
        if archetype == "twin":
            fingerprint = f"demotwin{task.pk:05d}"
            if twin_of is not None:
                # the partner must have a different variant of a personalised step, or equal solutions
                # would be expected and not worth a mention
                variants = len(variants_of(task.data))
                if variants > 1 and variant_index(user.pk, task.pk, variants) == variant_index(twin_of.pk, task.pk, variants):
                    fingerprint = f"demo{user.pk:05d}{task.pk:05d}"
        CodeRun.objects.create(
            user=user, task=task, outcome="success", exit_code=0, passed=True, attempt_no=fails + 1,
            code_length=length, provenance=provenance, fingerprint=fingerprint, ast_nodes=TWIN_NODES,
            constructs=[],
        )
        TaskProgress.objects.create(
            user=user, task=task, status="completed", attempts=fails + 1, last_submitted_at=last
        )
        return task.xp_reward
