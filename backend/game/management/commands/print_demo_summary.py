from django.core.management.base import BaseCommand
from game.models import Mission, Location


class Command(BaseCommand):
    help = "Print a short summary about demo data: locations and missions"

    def handle(self, *args, **options):
        loc_count = Location.objects.count()
        mis_count = Mission.objects.count()
        titles = list(
            Mission.objects.order_by("location__order", "order")
            .values_list("title", flat=True)[:10]
        )

        self.stdout.write(self.style.SUCCESS("Demo summary:"))
        self.stdout.write(f"  Locations: {loc_count}")
        self.stdout.write(f"  Missions:  {mis_count}")
        if titles:
            self.stdout.write("  Sample missions:")
            for t in titles:
                self.stdout.write(f"    - {t}")
        else:
            self.stdout.write("  No missions found. Run: python manage.py load_demo_content")
