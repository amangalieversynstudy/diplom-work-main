"""Management command: create the superuser named in DJANGO_SUPERUSER_* once, at deploy start."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Idempotent: nothing to do without the variables or when the account exists, so the start command needs no `|| true`."""

    help = "Create the superuser from DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD if it does not exist"

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        if not username:
            return
        User = get_user_model()
        if User.objects.filter(username__iexact=username).exists():
            self.stdout.write(f"Superuser {username}: already present, skipped.")
            return
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        if not password:
            # said in the deploy log; the site still starts, an admin account is not worth an outage
            self.stderr.write(f"Superuser {username}: DJANGO_SUPERUSER_PASSWORD is not set, not created.")
            return
        User.objects.create_superuser(
            username=username, email=os.getenv("DJANGO_SUPERUSER_EMAIL", ""), password=password
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser {username} created."))
