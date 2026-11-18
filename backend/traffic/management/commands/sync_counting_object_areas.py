from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from traffic.areas import sync_counting_object_areas


class Command(BaseCommand):
    help = (
        "Recompute the grid cells (ref_geo area types AREA_TYPES, e.g. M1 and "
        "M0.5) of every counting object, e.g. after loading or reloading "
        "ref_geo, or after changing the grids."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--area-type",
            action="append",
            dest="area_types",
            help=f"ref_geo type_code of a grid (repeatable; default: {', '.join(settings.AREA_TYPES)}).",
        )

    def handle(self, *args, area_types=None, **options):
        area_types = area_types or settings.AREA_TYPES
        inserted = sync_counting_object_areas(area_types=area_types)
        if inserted is None:
            raise CommandError("ref_geo schema missing: load it first.")
        self.stdout.write(
            self.style.SUCCESS(f"{inserted} object/cell pairs ({', '.join(area_types)}).")
        )
