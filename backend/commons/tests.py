import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
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


class PracticeApiTests(TestCase):
    url = "/api/commons/practice"

    def test_invalid_parent_id_is_400(self):
        for query in ("parent_id=abc", "parent_id=abc&recursive=true"):
            self.assertEqual(self.client.get(f"{self.url}?{query}").status_code, 400)

    def test_recursive_terminates_on_a_cycle(self):
        Practice.objects.filter(code="walking").update(
            parent=Practice.objects.get(code="hiking")
        )
        with connection.cursor() as cursor:
            # Fail instead of hanging if the query loops again.
            cursor.execute("SET LOCAL statement_timeout = 2000")
        response = self.client.get(f"{self.url}?parent_code=walking&recursive=true")
        self.assertEqual(response.status_code, 200)


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


class DataImportAddPageTests(TestCase):
    url = "/admin/commons/dataimport/add/"

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.org", "x"))

    def test_expected_file_of_each_source_is_shown(self):
        response = self.client.get(self.url)
        strava = DataSource.objects.get(code="strava")
        self.assertContains(response, 'id="import-example"')
        self.assertContains(response, f"&quot;{strava.pk}&quot;: {{&quot;content&quot;: &quot;Contient des tron")
        self.assertContains(response, "&quot;example&quot;: &quot;Zip Strava Metro")

    def test_refused_file_shows_the_error_and_keeps_nothing(self):
        strava = DataSource.objects.get(code="strava")
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                self.url,
                {"source": strava.pk, "file": SimpleUploadedFile("export.zip", b"not a zip"),
                 "line_numbers": 0, "error_numbers": 0},
                follow=True,
            )
            self.assertEqual(list(Path(media_root).rglob("*.*")), [])
        # Back to the form with the same source, and the parser's message.
        self.assertEqual(response.redirect_chain, [(f"{self.url}?source={strava.pk}", 302)])
        self.assertContains(response, "Import refusé")
        self.assertContains(response, "Le fichier Strava doit être un zip")
        self.assertFalse(DataImport.objects.exists())


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


class ParserExamplesTests(SimpleTestCase):
    def test_every_parser_describes_its_file(self):
        from django.utils.module_loading import import_string

        from .models import PARSERS

        for code, path in PARSERS.items():
            with self.subTest(code):
                self.assertTrue(import_string(path).EXAMPLE)
