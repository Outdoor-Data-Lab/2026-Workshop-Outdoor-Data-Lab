from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection


class Command(BaseCommand):
    help = "Load the traffic demonstration data (needs ref_geo)."

    def handle(self, *args, **options):
        script_path = (
            Path(settings.BASE_DIR)
            / "workshop2026"
            / "processing"
            / "insert_traffic_data.sql"
        )
        try:
            sql_script = script_path.read_text(encoding="utf-8")
        except OSError as error:
            raise CommandError(f"Could not read SQL script at {script_path}: {error}") from error

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_script)
        except DatabaseError as error:
            connection.rollback()
            raise CommandError(f"Could not execute SQL script: {error}") from error

        self.stdout.write(self.style.SUCCESS("Traffic demonstration data loaded."))
