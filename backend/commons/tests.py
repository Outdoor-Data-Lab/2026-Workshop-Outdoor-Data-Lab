import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import PARSERS, DataImport, DataSource, Practice, register_parsers


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
                "outdoorvision", "ecocompteur", "strava", "geotrek", "gbif", "sinp",
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
    url = "/api/commons/practices"

    def codes(self, query):
        response = self.client.get(f"{self.url}?{query}&limit=100")
        self.assertEqual(response.status_code, 200)
        return {p["code"] for p in response.json()["results"]}

    def test_filters(self):
        self.assertEqual(self.codes("parent_code=walking"), {"hiking", "snowshoeing"})
        self.assertEqual(self.codes("code=gravel"), {"gravel"})
        self.assertNotIn("hiking", self.codes("has_parent=false"))
        self.assertNotIn("walking", self.codes("has_parent=True"))

    def test_recursive_returns_every_descendant(self):
        Practice.objects.create(code="nordic_walking", label="Marche nordique",
                                parent=Practice.objects.get(code="hiking"))
        self.assertEqual(
            self.codes("parent_code=walking&recursive=true"),
            {"hiking", "snowshoeing", "nordic_walking"},
        )

    def test_relations_exposed_by_code(self):
        response = self.client.get(f"{self.url}?code=gravel")
        self.assertEqual(response.json()["results"][0]["parent_code"], "cycling")

    def test_recursive_terminates_on_a_cycle(self):
        Practice.objects.filter(code="walking").update(
            parent=Practice.objects.get(code="hiking")
        )
        with connection.cursor() as cursor:
            # Fail instead of hanging if the query loops again.
            cursor.execute("SET LOCAL statement_timeout = 2000")
        response = self.client.get(f"{self.url}?parent_code=walking&recursive=true")
        self.assertEqual(response.status_code, 200)
    def test_dynamic_fields_filtering(self):
        """Test DynamicFieldsMixin filters fields correctly for all serializers in commons.api.serializers."""
        # Test PracticeSerializer
        response = self.client.get(f"{self.url}?fields=id,code")
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertIn("id", result)
        self.assertIn("code", result)
        self.assertNotIn("label", result)
        self.assertNotIn("parent_code", result)
        # Verify only requested fields exist
        self.assertEqual(set(result.keys()), {"id", "code"})


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
        self.assertIsNone(self.make_import("geotrek").run_parser())


class ImportAdminTests(TestCase):
    """The import pages of the domains share commons.admin.ImportAdmin."""

    def setUp(self):
        self.media = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.media))
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.com", "password"))
        self.traffic_url = reverse("admin:traffic_trafficimport_add")
        self.biodiversity_url = reverse("admin:biodiversity_observationimport_add")

    def add_import(self, url, source_code, content=b"content", name="data.csv"):
        return self.client.post(
            url,
            {
                "source": DataSource.objects.get(code=source_code).pk,
                "file": SimpleUploadedFile(name, content),
                "line_numbers": 0,
                "error_numbers": 0,
            },
            follow=True,
        )

    def test_each_page_offers_the_sources_of_its_domain(self):
        traffic = self.client.get(self.traffic_url)
        self.assertContains(traffic, ">Strava</option>")
        self.assertNotContains(traffic, ">SINP</option>")
        biodiversity = self.client.get(self.biodiversity_url)
        self.assertContains(biodiversity, ">SINP</option>")
        self.assertNotContains(biodiversity, ">Strava</option>")

    def test_expected_file_of_each_source_is_shown(self):
        response = self.client.get(self.traffic_url)
        strava = DataSource.objects.get(code="strava")
        self.assertContains(response, 'id="import-example"')
        self.assertContains(response, f"&quot;{strava.pk}&quot;: {{&quot;content&quot;: &quot;Holds trail and road edges")
        self.assertContains(response, "&quot;example&quot;: &quot;Yearly or daily Strava Metro zip")

    def test_refused_file_shows_the_error_and_keeps_nothing(self):
        strava = DataSource.objects.get(code="strava")
        response = self.add_import(self.traffic_url, "strava", b"not a zip", "export.zip")
        self.assertEqual(list(self.media.rglob("*.*")), [])
        # Back to the form with the same source, and the parser's message.
        self.assertEqual(response.redirect_chain, [(f"{self.traffic_url}?source={strava.pk}", 302)])
        self.assertContains(response, "Import refused, nothing was saved")
        self.assertContains(response, "The Strava file must be a zip")
        self.assertFalse(DataImport.objects.exists())

    def test_form_asks_only_for_the_source_and_the_file(self):
        # The parser fills line_numbers and error_numbers: the user must not set them.
        for url in (self.traffic_url, self.biodiversity_url, reverse("admin:outdoor_offerimport_add")):
            with self.subTest(url):
                form = self.client.get(url).context["adminform"].form
                self.assertEqual(list(form.fields), ["source", "file"])

    def test_source_of_another_domain_is_rejected(self):
        response = self.add_import(self.biodiversity_url, "strava")
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(DataImport.objects.exists())

    @patch("biodiversity.parsers.sinp.SINPParser")
    def test_imported_at_once_without_preview(self, parser_class):
        parser_class.return_value.errors = []
        parser_class.return_value.import_data.return_value = 12
        response = self.add_import(self.biodiversity_url, "sinp")
        parser_class.return_value.preview.assert_not_called()  # the file is read once
        self.assertContains(response, "12 item(s) imported, 0 line(s) in error.")
        self.assertEqual(DataImport.objects.get().source.code, "sinp")


class DataImportHistoryTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.com", "password"))
        for code in ("strava", "sinp"):
            DataImport.objects.create(source=DataSource.objects.get(code=code), file=f"imports/{code}.csv")

    def test_history_lists_every_import_but_adds_none(self):
        response = self.client.get(reverse("admin:commons_dataimport_changelist"))
        self.assertContains(response, "imports/strava.csv")
        self.assertContains(response, "imports/sinp.csv")
        self.assertEqual(self.client.get(reverse("admin:commons_dataimport_add")).status_code, 403)

    def test_a_domain_page_lists_its_imports_only(self):
        response = self.client.get(reverse("admin:traffic_trafficimport_changelist"))
        self.assertContains(response, "imports/strava.csv")
        self.assertNotContains(response, "imports/sinp.csv")


class RegisterParsersTests(SimpleTestCase):
    def test_a_source_has_a_single_parser(self):
        with self.assertRaises(ImproperlyConfigured):
            register_parsers({"strava": "biodiversity.parsers.gbif.GBIFParser"})
        register_parsers({"strava": PARSERS["strava"]})  # registering it again changes nothing

    def test_every_domain_registered_its_parsers(self):
        self.assertLessEqual({"outdoorvision", "strava", "ecocompteur", "inaturalist", "sinp", "gbif"}, set(PARSERS))

    def test_every_parser_shares_the_import_base(self):
        from django.utils.module_loading import import_string

        from .parsers import ImportParser

        for code, path in PARSERS.items():
            with self.subTest(code):
                self.assertTrue(issubclass(import_string(path), ImportParser))


class ParserExamplesTests(SimpleTestCase):
    def test_every_parser_describes_its_file(self):
        from django.utils.module_loading import import_string

        from .models import PARSERS

        for code, path in PARSERS.items():
            with self.subTest(code):
                self.assertTrue(import_string(path).EXAMPLE)
