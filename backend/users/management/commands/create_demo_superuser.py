import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings


class Command(BaseCommand):
    help = "Create a demo superuser from environment variables if it doesn't exist"

    def handle(self, *args, **options):
        allow_env = os.getenv("ALLOW_DEMO_SEED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not settings.DEBUG and not allow_env:
            self.stdout.write(
                self.style.WARNING(
                    "Demo superuser creation is disabled in non-debug environments. "
                    "Set ALLOW_DEMO_SEED=true to force."
                )
            )
            return
        User = get_user_model()
        username = os.getenv("DEMO_ADMIN_USERNAME", "admin")
        email = os.getenv("DEMO_ADMIN_EMAIL", "admin@example.com")
        password = os.getenv("DEMO_ADMIN_PASSWORD", "admin123")

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING("Superuser already exists."))
            return

        user = User.objects.create_superuser(
            username=username, email=email, password=password
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser created: {user.username}"))
