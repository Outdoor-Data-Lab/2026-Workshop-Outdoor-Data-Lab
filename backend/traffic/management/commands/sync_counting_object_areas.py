from django.core.management.base import BaseCommand, CommandError

from traffic.areas import sync_counting_object_areas


class Command(BaseCommand):
    help = (
        "Recompute the 1 km grid cells (ref_geo M1) of every counting object, "
        "e.g. after loading or reloading ref_geo."
    )

    def handle(self, *args, **options):
        inserted = sync_counting_object_areas()
        if inserted is None:
            raise CommandError("ref_geo schema missing: load it first.")
        self.stdout.write(self.style.SUCCESS(f"{inserted} object/cell pairs."))
