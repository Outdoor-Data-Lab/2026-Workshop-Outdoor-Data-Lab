from django.core.management.base import BaseCommand

from traffic.areas import refresh_cell_day_counts


class Command(BaseCommand):
    help = (
        "Rebuild the precomputed counts per (cell, source, day) that the scores read. "
        "Run it after sync_counting_object_areas, deleting an import or loading data "
        "outside the import pages; until then the scores read the measures (slower)."
    )

    def handle(self, *args, **options):
        rows = refresh_cell_day_counts()
        self.stdout.write(self.style.SUCCESS(f"{rows} (cell, source, day) rows."))
