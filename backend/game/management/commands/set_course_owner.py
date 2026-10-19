"""Give a teacher ownership of a course, so their cabinet shows its learners.

    python manage.py set_course_owner python-intro teacher_username

A teacher (staff, not superuser) sees analytics and the roster only for courses
they own. The built-in course is seeded without an owner, so without this step
a teacher running a pilot would open an empty dashboard.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from game.classes import is_vetted_teacher
from game.models import Track


class Command(BaseCommand):
    help = "Set the teacher who owns a course (track)."

    def add_arguments(self, parser):
        parser.add_argument("track", help="Slug of the track, e.g. python-intro.")
        parser.add_argument("teacher", help="Username of a staff account.")
        parser.add_argument(
            "--transfer-class",
            action="store_true",
            help="Move a class that already has learners to another teacher.",
        )

    def handle(self, *args, **options):
        try:
            track = Track.objects.get(slug=options["track"])
        except Track.DoesNotExist:
            raise CommandError(f"No track with slug {options['track']!r}.")
        try:
            teacher = get_user_model().objects.get(username=options["teacher"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"No user named {options['teacher']!r}.")
        if track.is_public and not is_vetted_teacher(teacher):
            raise CommandError(
                f"{teacher.username} is not a vetted teacher: the owner of a public course sees every learner who "
                "opens it, so only staff (invite code or admin) may own one."
            )
        if (
            track.owner_id not in (None, teacher.pk)
            and track.enrollments.exists()
            and not options.get("transfer_class")
        ):
            raise CommandError(
                "This class has learners who agreed to be seen by its current teacher. "
                "Pass --transfer-class only if they were told about the new teacher."
            )
        if not teacher.can_teach:
            raise CommandError(
                f"{teacher.username} is not a teacher or staff: only teachers can own a course."
            )
        previous = track.owner.username if track.owner_id else "nobody"
        track.owner = teacher
        track.save(update_fields=["owner"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{track.slug}: owner {previous} -> {teacher.username}"
            )
        )
