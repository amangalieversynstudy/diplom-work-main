"""Email a streak reminder to players whose streak is about to break.

A streak is "at risk" when the player extended it *yesterday* but hasn't
completed anything *today* yet (mirrors ``Profile.streak_at_risk``). This
command finds those players and emails a nudge.

Designed to run once a day from a scheduler (e.g. Railway cron / a periodic
job):

    python manage.py send_streak_reminders

Idempotent within a day: ``Profile.last_streak_reminder`` is stamped after a
send, so re-running the same day won't double-email. Use ``--dry-run`` to list
recipients without sending.
"""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import Profile


class Command(BaseCommand):
    help = "Email a reminder to players whose daily streak is at risk."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List who would be reminded without sending any email.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # At risk: streak alive (last activity yesterday), not yet extended
        # today, has a usable email, active account, not already reminded today.
        recipients = (
            Profile.objects.select_related("user")
            .filter(
                current_streak__gte=1,
                last_streak_date=yesterday,
                user__is_active=True,
            )
            .exclude(user__email="")
            .exclude(last_streak_reminder=today)
        )

        frontend_url = (
            getattr(settings, "FRONTEND_URL", None) or "http://localhost:3000"
        ).rstrip("/")

        dry_run = options["dry_run"]
        sent = 0
        for profile in recipients:
            user = profile.user
            if dry_run:
                self.stdout.write(
                    f"  would remind {user.username} <{user.email}> "
                    f"(streak={profile.current_streak})"
                )
                continue

            send_mail(
                "🔥 Не теряй свою серию — RPG Academy",
                (
                    f"Привет, {user.username}!\n\n"
                    f"Твоя серия — {profile.current_streak} дн. подряд. "
                    "Сегодня ты ещё не прошёл ни одной миссии — заверши хотя бы "
                    "одну, чтобы серия не оборвалась.\n\n"
                    f"К миссиям: {frontend_url}/worlds\n\n"
                    "Так держать! 🗡️"
                ),
                None,  # → DEFAULT_FROM_EMAIL
                [user.email],
                fail_silently=True,
            )
            profile.last_streak_reminder = today
            profile.save(update_fields=["last_streak_reminder"])
            sent += 1

        verb = "would remind" if dry_run else "reminded"
        count = recipients.count() if dry_run else sent
        self.stdout.write(self.style.SUCCESS(f"Streak reminders — {verb}: {count}"))
