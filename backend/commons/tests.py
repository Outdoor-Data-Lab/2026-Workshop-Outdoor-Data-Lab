import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase, override_settings

from .models import DataImport, DataSource, Practice


class CommonsTests(TestCase):
    def test_tables_are_in_commons_schema(self):
        with connection.cursor() as cursor:
            cursor.execute("select tablename from pg_tables where schemaname = 'commons'")
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(tables, {"data_sources", "data_imports", "practices"})

    def test_initial_data_sources(self):
        self.assertEqual(
            set(DataSource.objects.values_list("code", flat=True)),
            {
                "outdoorvision", "ecocompteur", "strava", "geotrek", "gbif", "inpn",
                "geonature", "inaturalist", "garmin", "komoot", "visorando",
            },
        )

    def test_source_with_imports_cannot_be_deleted(self):
        source = DataSource.objects.get(code="gbif")
        DataImport.objects.create(source=source, file="gbif.csv", line_numbers=10, error_numbers=1)
        with self.assertRaises(ProtectedError):
            source.delete()


class PracticeTests(TestCase):
    def test_initial_practice_hierarchy(self):
        self.assertEqual(
            dict(Practice.objects.values_list("code", "parent__code")),
            {
                # Broad practices
                "walking": None,
                "running": None,
                "cycling": None,
                "flying": None,
                "boating": None,
                "climbing": None,
                "skiing": None,
                "riding": None,
                # Finer practices
                "hiking": "walking",
                "snowshoeing": "walking",
                "trail_running": "running",
                "mountain_biking": "cycling",
                "road_cycling": "cycling",
                "gravel": "cycling",
                "alpine_skiing": "skiing",
                "ski_touring": "skiing",
                "kayaking": "boating",
                "canyoning": "boating",
                "rock_climbing": "climbing",
                "via_ferrata": "climbing",
                "mountaineering": "climbing",
                "paragliding": "flying",
                "horse_riding": "riding",
            },
        )

    def test_parent_with_children_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            Practice.objects.get(code="cycling").delete()

    def test_practice_cannot_be_its_own_parent(self):
        practice = Practice.objects.get(code="gravel")
        practice.parent_id = practice.id
        with self.assertRaises(IntegrityError), transaction.atomic():
            practice.save()


class DataImportFileTests(TestCase):
    def test_uploaded_file_is_stored_under_media_imports(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            data_import = DataImport.objects.create(
                source=DataSource.objects.get(code="outdoorvision"),
                file=SimpleUploadedFile("tracks.gpkg", b"content"),
            )
            self.assertTrue(data_import.file.name.startswith("imports/tracks"))
            self.assertEqual(
                Path(media_root, data_import.file.name).read_bytes(), b"content"
            )
            with data_import.file.open("rb") as stored:
                self.assertEqual(stored.read(), b"content")


class DataImportParserTests(SimpleTestCase):
    def make_import(self, source_code="outdoorvision"):
        data_import = DataImport(
            source=DataSource(code=source_code, label=source_code),
            file="imports/outdoorvision.gpkg",
        )
        data_import.pk = 1
        return data_import

    @patch("traffic.parsers.outdoorvision.OutdoorVisionParser")
    def test_run_outdoorvision_parser(self, parser_class):
        data_import = self.make_import()
        parser_class.return_value.import_data.return_value = 2

        result = data_import.run_parser()

        parser_class.assert_called_once_with(data_import)
        parser_class.return_value.import_data.assert_called_once_with()
        self.assertEqual(result, 2)

    def test_source_without_parser_is_ignored(self):
        self.assertIsNone(self.make_import("gbif").run_parser())
