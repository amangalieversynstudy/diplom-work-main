"""Seed демо-героев для лидерборда.

Создаёт 6 RPG-персонажей с фиксированными username/xp/streak и
обновляет соответствующие LeaderboardEntry строки. Идемпотентно —
повторный запуск не создаёт дублей, только переписывает значения.

Использование:
    python manage.py seed_leaderboard
    python manage.py seed_leaderboard --reset   # снести heroes:* и пересоздать
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import User
from game.models import ClassRole, LeaderboardEntry


HEROES = [
    # (username, display_name, xp, streak, class_name)
    ("aelthorn",      "Aelthorn the Bytemage",   3120, 27, "Python-спеллблейд"),
    ("vyrelinde",     "Vyrelinde Stormcaster",   2845, 19, "Арканист Django"),
    ("ragnar_void",   "Ragnar Voidwalker",       2410, 31, "DevOps-рейнджер"),
    ("ilyana_quill",  "Ilyana Quillweaver",      1980,  8, "Python-спеллблейд"),
    ("morthus_iron",  "Morthus Ironbrand",       1455, 14, "DevOps-рейнджер"),
    ("seraphi_dawn",  "Seraphi Dawnsong",         990,  4, "Арканист Django"),
]


class Command(BaseCommand):
    help = "Seed 6 RPG-styled demo heroes into Profile + LeaderboardEntry."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Снести существующих heroes-* перед пересозданием.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            removed = User.objects.filter(username__in=[h[0] for h in HEROES]).delete()
            self.stdout.write(self.style.WARNING(
                f"Удалено пользователей: {removed[0]}"
            ))

        # Подгружаем классы один раз (создаём при отсутствии)
        class_cache = {}
        for cls_name in {h[4] for h in HEROES}:
            obj, _ = ClassRole.objects.get_or_create(name=cls_name)
            class_cache[cls_name] = obj

        for username, display_name, xp, streak, cls_name in HEROES:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@rpg.academy",
                    "display_name": display_name,
                    "is_active": True,
                },
            )
            if not created:
                user.display_name = display_name
                user.email = f"{username}@rpg.academy"
                user.is_active = True
                user.save(update_fields=["display_name", "email", "is_active"])

            # Profile создаётся signal'ом post_save на User → достаём и
            # обновляем XP/streak/класс.
            profile = user.profile
            profile.xp = xp
            profile.level = (xp // 100) + 1
            profile.current_streak = streak
            profile.longest_streak = max(profile.longest_streak, streak)
            profile.class_role = class_cache[cls_name]
            profile.save()

            # LeaderboardEntry — global scope, all_time period
            entry, _ = LeaderboardEntry.objects.update_or_create(
                user=user,
                scope="global",
                period_label="all_time",
                track=None,
                defaults={
                    "xp_total": xp,
                    "snapshot_at": timezone.now(),
                },
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {display_name:30}  XP={xp:>4}  streak={streak:>2}  ({cls_name})"
            ))

        # Пересчитываем position по XP DESC, streak DESC
        ordered = (
            LeaderboardEntry.objects
            .filter(scope="global", period_label="all_time")
            .select_related("user__profile")
            .order_by("-xp_total", "-user__profile__current_streak")
        )
        for idx, entry in enumerate(ordered, start=1):
            if entry.position != idx:
                entry.position = idx
                entry.save(update_fields=["position"])

        self.stdout.write(self.style.SUCCESS(
            f"\n✔ Лидерборд пересчитан, всего записей: {ordered.count()}"
        ))
