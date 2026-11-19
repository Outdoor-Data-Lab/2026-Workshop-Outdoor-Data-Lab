import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from ref_geo.models import BibAreasType, LArea

from .models import (
    PARSERS,
    DataImport,
    DataSource,
    ExternalLayer,
    InstanceSettings,
    LayerGroup,
    LayerOrder,
    Practice,
    register_parsers,
)
from .tasks import run_import


class CommonsTests(TestCase):
    def test_tables_are_in_commons_schema(self):
        with connection.cursor() as cursor:
            cursor.execute("select tablename from pg_tables where schemaname = 'commons'")
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(tables, {"data_sources", "data_imports", "practices", "external_layers", "instance_settings", "layer_groups", "layer_orders"})

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


class ExternalLayerApiTests(TestCase):
    def test_layer_exposed(self):
        ExternalLayer.objects.create(
            label="Zones sensibles",
            url="https://example.org/zones.geojson",
            description="Données : Biodiv'Sports",
            properties=["name"],
            label_property="name",
            color_property="species_id",
            colors={"7": "#c0392b"},
        )
        response = self.client.get("/api/commons/external-layers")
        self.assertEqual(response.status_code, 200)
        layer = response.json()["results"][0]
        self.assertEqual(
            (layer["description"], layer["properties"], layer["label_property"], layer["colors"]),
            ("Données : Biodiv'Sports", ["name"], "name", {"7": "#c0392b"}),
        )


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
    def make_import(self, format_code="outdoorvision"):
        data_import = DataImport(
            format=format_code,
            source=DataSource(code="geotrek", label="Geotrek"),
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

    def test_format_without_parser_is_ignored(self):
        self.assertIsNone(self.make_import("unknown").run_parser())


class ImportAdminTests(TestCase):
    """The import pages of the domains share commons.admin.ImportAdmin."""

    def setUp(self):
        self.media = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.media))
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.com", "password"))
        self.traffic_url = reverse("admin:traffic_trafficimport_add")
        self.biodiversity_url = reverse("admin:biodiversity_observationimport_add")

    def add_import(self, url, format_code, source_code, content=b"content", name="data.csv"):
        return self.client.post(
            url,
            {
                "format": format_code,
                "source": DataSource.objects.get(code=source_code).pk,
                "file": SimpleUploadedFile(name, content),
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

    def test_a_source_may_serve_several_domains(self):
        # iNaturalist: observers for traffic, occurrences for biodiversity.
        for url in (self.traffic_url, self.biodiversity_url):
            with self.subTest(url):
                self.assertContains(self.client.get(url), ">iNaturalist</option>")

    def test_each_page_offers_the_formats_of_its_domain(self):
        formats = self.client.get(self.traffic_url).context["adminform"].form.fields["format"]
        self.assertEqual(
            [code for code, _ in formats.choices], ["", "outdoorvision", "strava", "counter", "inaturalist"]
        )
        offers = self.client.get(reverse("admin:outdoor_offerimport_add")).context["adminform"].form
        self.assertEqual(offers["format"].initial, "offers")  # a single format is preselected

    def test_expected_file_of_each_format_is_shown(self):
        response = self.client.get(self.traffic_url)
        self.assertContains(response, 'id="import-example"')
        self.assertContains(response, "&quot;strava&quot;: {&quot;content&quot;: &quot;Holds trail and road edges")
        self.assertContains(response, "&quot;example&quot;: &quot;Yearly or daily Strava Metro zip")

    def test_file_refused_by_the_worker_is_kept_as_failed(self):
        self.add_import(self.traffic_url, "strava", "strava", b"not a zip", "export.zip")
        data_import = DataImport.objects.get()
        self.assertEqual(data_import.status, DataImport.Status.FAILED)
        self.assertIn("File refused, nothing imported: The Strava file must be a zip", data_import.message)
        # The file is deleted.
        self.assertEqual(data_import.file.name, "")
        self.assertEqual(list(self.media.rglob("*.*")), [])

    def test_form_asks_only_for_the_format_the_source_and_the_file(self):
        # The parser fills line_numbers and error_numbers: the user must not set them.
        for url in (self.traffic_url, self.biodiversity_url, reverse("admin:outdoor_offerimport_add")):
            with self.subTest(url):
                form = self.client.get(url).context["adminform"].form
                self.assertEqual(list(form.fields), ["format", "source", "file"])

    def test_source_of_another_domain_is_rejected(self):
        response = self.add_import(self.biodiversity_url, "sinp", "strava")
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(DataImport.objects.exists())

    @patch("biodiversity.parsers.sinp.SINPParser")
    def test_sent_to_the_worker_without_preview(self, parser_class):
        # Texts of the class: shown in the format choice, and they must be strings.
        parser_class.LABEL = parser_class.CONTENT = parser_class.EXAMPLE = "SINP"
        parser_class.return_value.errors = []
        parser_class.return_value.import_data.return_value = 12
        with patch("commons.admin.run_import.delay") as delay:
            response = self.add_import(self.biodiversity_url, "sinp", "sinp")
        data_import = DataImport.objects.get()
        delay.assert_called_once_with(data_import.pk)
        self.assertContains(response, "Import queued")
        self.assertEqual((data_import.source.code, data_import.status), ("sinp", DataImport.Status.PENDING))

        run_import(data_import.pk)  # what the worker does
        parser_class.return_value.preview.assert_not_called()  # the file is read once
        data_import.refresh_from_db()
        self.assertEqual(data_import.status, DataImport.Status.DONE)
        self.assertEqual(data_import.message, "12 item(s) imported, 0 line(s) in error.")


class DataSourceAdminTests(TestCase):
    def test_a_new_source_is_offered_on_the_pages_of_its_domains(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.com", "password"))
        self.client.post(
            reverse("admin:commons_datasource_add"),
            {"code": "geotrek_pne", "label": "Geotrek PNE", "domains": ["outdoor"]},
        )
        self.assertEqual(DataSource.objects.get(code="geotrek_pne").domains, ["outdoor"])
        self.assertContains(self.client.get(reverse("admin:outdoor_offerimport_add")), ">Geotrek PNE</option>")
        self.assertNotContains(self.client.get(reverse("admin:traffic_trafficimport_add")), ">Geotrek PNE</option>")


class DataImportHistoryTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.com", "password"))
        for code in ("strava", "sinp"):
            DataImport.objects.create(format=code, source=DataSource.objects.get(code=code), file=f"imports/{code}.csv")

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
    def test_a_format_has_a_single_parser(self):
        with self.assertRaises(ImproperlyConfigured):
            register_parsers({"strava": "biodiversity.parsers.gbif.GBIFParser"})
        register_parsers({"strava": PARSERS["strava"]})  # registering it again changes nothing

    def test_every_domain_registered_its_parsers(self):
        self.assertEqual(
            set(PARSERS), {"outdoorvision", "strava", "counter", "inaturalist", "sinp", "gbif", "offers"}
        )

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
                parser = import_string(path)
                self.assertTrue(parser.LABEL and parser.EXAMPLE)


class LayerOrderTests(TestCase):
    def test_admin_lists_every_layer_of_the_map_by_section(self):
        layer = ExternalLayer.objects.create(label="Suricate", url="https://example.org/a.geojson")
        LayerGroup.objects.filter(code="outdoor").update(order=1)
        LayerOrder.objects.create(layer="traffic/area", group=LayerGroup.objects.get(code="traffic"), label="Old", order=5)
        LayerOrder.objects.create(layer="external/999", group=LayerGroup.objects.get(code="external"), label="Gone", order=1)
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.org", "admin"))

        response = self.client.get(reverse("admin:commons_layerorder_changelist"))

        self.assertContains(response, "Suricate")
        self.assertEqual(list(LayerOrder.objects.values_list("group__code", "layer", "label", "order")), [
            ("outdoor", "outdoor/offer", "Offres outdoor", 10),  # its section first
            ("grid", "traffic/area", "Fréquentation par maille", 5),  # kept its rank, new section and label
            ("grid", "biodiversity/area", "Taxons menacés par maille", 15),  # new ones last in their section
            ("traffic", "traffic/counter", "Compteur", 10),
            ("traffic", "traffic/segment", "Segment", 20),
            ("external", f"external/{layer.pk}", "Suricate", 10),
        ])


class InstanceSettingsApiTests(TestCase):
    url = "/api/commons/instance-settings"

    def test_no_default_area(self):
        self.assertEqual(
            self.client.get(self.url).json(),
            {"default_area": None, "grid_area_type": settings.DEFAULT_GRID_AREA_TYPE,
             "group_order": {"grid": 10, "traffic": 20, "biodiversity": 30, "outdoor": 40, "external": 50}, "layer_order": {}},
        )

    def test_layer_order(self):
        LayerOrder.objects.create(layer="traffic/area", group=LayerGroup.objects.get(code="traffic"), order=1)
        LayerOrder.objects.create(layer="external/3", group=LayerGroup.objects.get(code="external"), order=2)
        self.assertEqual(self.client.get(self.url).json()["layer_order"], {"traffic/area": 1, "external/3": 2})

    def test_default_area(self):
        # ref_geo is not created by the migrations of the test database.
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS ref_geo")
        with connection.schema_editor() as editor:
            for model in (BibAreasType, LArea):
                editor.create_model(model)
        park = BibAreasType.objects.create(type_name="Parcs nationaux", type_code="PN")
        area = LArea.objects.create(id_area=7, type=park, area_name="Écrins", area_code="PNE")
        instance = InstanceSettings.load()
        instance.default_area = area
        instance.save()

        self.assertEqual(self.client.get(self.url).json(), {
            "default_area": {"id_area": 7, "area_name": "Écrins", "area_code": "PNE", "type_code": "PN"},
            "grid_area_type": settings.DEFAULT_GRID_AREA_TYPE,
            "group_order": {"grid": 10, "traffic": 20, "biodiversity": 30, "outdoor": 40, "external": 50},
            "layer_order": {},
        })
        self.assertEqual(InstanceSettings.objects.count(), 1)
