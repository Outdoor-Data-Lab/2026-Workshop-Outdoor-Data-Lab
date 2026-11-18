import json
import tempfile
import uuid
from pathlib import Path

import geopandas as gpd
import shapely
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString, Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from commons.models import DataImport, DataSource, Practice

from .models import Offer, OfferImport
from .parsers import OfferParser


class OutdoorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Seeded by commons 0002.
        cls.source = DataSource.objects.get(code="geotrek")
        cls.hiking = Practice.objects.get(code="hiking")

    def make_offer(self, **kwargs):
        values = {"practice": self.hiking, "source": self.source, "geom": Point(6.4, 44.9, srid=4326)}
        return Offer.objects.create(**(values | kwargs))


class SchemaTests(TestCase):
    def test_tables_are_in_outdoor_schema(self):
        with connection.cursor() as cursor:
            cursor.execute("select tablename from pg_tables where schemaname = 'outdoor'")
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(tables, {"offers"})


class OfferTests(OutdoorTestCase):
    def test_any_geometry_type(self):
        trail = self.make_offer(geom=LineString((6.4, 44.9), (6.5, 45.0), srid=4326))
        self.assertEqual(trail.geom.geom_type, "LineString")

    def test_any_practice_level(self):
        self.make_offer(practice=Practice.objects.get(code="climbing"))
        self.make_offer(practice=Practice.objects.get(code="via_ferrata"))
        self.assertEqual(Offer.objects.filter(practice__code__in=["climbing", "via_ferrata"]).count(), 2)

    def test_external_id_unique_per_source(self):
        self.make_offer(external_id="42")
        with self.assertRaises(IntegrityError):
            self.make_offer(external_id="42")

    def test_offers_without_external_id_are_not_unique(self):
        self.make_offer()
        self.make_offer()
        self.assertEqual(Offer.objects.count(), 2)

    def test_practice_in_use_is_protected(self):
        self.make_offer()
        with self.assertRaises(ProtectedError):
            self.hiking.delete()


def gpkg(rows, crs=4326, other_layer=False) -> bytes:
    """GeoPackage content with one layer of offers (two with other_layer)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "offers.gpkg")
        gpd.GeoDataFrame(rows, geometry="geometry", crs=crs).to_file(path, layer="offres")
        if other_layer:
            gpd.GeoDataFrame(rows, geometry="geometry", crs=crs).to_file(path, layer="autres")
        return path.read_bytes()


def line(external_id, practice="hiking", geometry=None, **columns):
    return {
        "id": external_id,
        "name": f"Offre {external_id}",
        "practice": practice,
        "geometry": shapely.Point(6.4, 44.9) if geometry is None else geometry,
        **columns,
    }


class OfferImportTestCase(OutdoorTestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=media.name))

    def make_import(self, content):
        return DataImport.objects.create(source=self.source, file=SimpleUploadedFile("offres.gpkg", content))

    def run_import(self, content):
        data_import = self.make_import(content)
        OfferParser(data_import).import_data()
        return data_import

    def offers(self):
        return {o.external_id: o for o in Offer.objects.filter(source=self.source)}


class OfferParserTests(OfferImportTestCase):
    def test_points_lines_polygons_other_columns_ignored(self):
        some_uuid = uuid.uuid4()
        data_import = self.run_import(
            gpkg(
                [
                    line("site", "rock_climbing", uuid=str(some_uuid), duree="2h"),
                    line("rando", geometry=shapely.LineString([(6.1, 44.7, 1200), (6.2, 44.8, 1500)])),
                    line("zone", "climbing", geometry=shapely.box(6.0, 44.5, 6.1, 44.6)),
                    line("zones", "snowshoeing", geometry=shapely.MultiPolygon(
                        [shapely.box(6.3, 44.6, 6.31, 44.61), shapely.box(6.4, 44.6, 6.41, 44.61)]
                    )),
                    line("take-off", "paragliding", geometry=shapely.GeometryCollection(
                        [shapely.LineString([(6.5, 44.5), (6.51, 44.51)]), shapely.box(6.5, 44.5, 6.52, 44.52)]
                    )),
                ]
            )
        )
        offers = self.offers()
        self.assertEqual((data_import.line_numbers, data_import.error_numbers), (5, 0))
        self.assertEqual(
            {k: o.geom.geom_type for k, o in offers.items()},
            {"site": "Point", "rando": "LineString", "zone": "Polygon", "zones": "MultiPolygon",
             "take-off": "GeometryCollection"},
        )
        self.assertFalse(offers["rando"].geom.hasz)
        self.assertEqual(offers["site"].name, "Offre site")
        self.assertEqual(offers["site"].practice.code, "rock_climbing")
        self.assertEqual(offers["site"].uuid, some_uuid)
        self.assertIsNone(offers["rando"].uuid)

    def test_lambert93_is_reprojected(self):
        point = gpd.GeoSeries([shapely.Point(6.4, 44.9)], crs=4326).to_crs(2154)[0]
        self.run_import(gpkg([line("site", geometry=point)], crs=2154))
        geom = self.offers()["site"].geom
        self.assertEqual(geom.srid, 4326)
        self.assertAlmostEqual(geom.x, 6.4, places=6)
        self.assertAlmostEqual(geom.y, 44.9, places=6)

    def test_lines_in_error_are_skipped_and_counted(self):
        taken = uuid.uuid4()
        self.make_offer(source=DataSource.objects.get(code="visorando"), uuid=taken)
        twice = str(uuid.uuid4())
        bowtie = shapely.Polygon([(6.2, 44.8), (6.3, 44.9), (6.3, 44.8), (6.2, 44.9)])
        data_import = self.make_import(
            gpkg(
                [
                    line("ok"),
                    line("bowtie", geometry=bowtie),  # invalid: repaired
                    line("unknown-practice", "Parapente"),
                    line("no-practice", None),
                    line(""),
                    line(None),
                    line("no-name", name=""),
                    line("null-name", name=None),
                    {**line("no-geometry"), "geometry": None},
                    line("empty-geometry", geometry=shapely.Point()),
                    line("empty-collection", geometry=shapely.GeometryCollection()),
                    line("bad-uuid", uuid="not-a-uuid"),
                    line("double"),
                    line("double"),
                    line("uuid-1", uuid=twice),
                    line("uuid-2", uuid=twice),
                    line("uuid-taken", uuid=str(taken)),
                ]
            )
        )
        parser = OfferParser(data_import)
        parser.import_data()
        offers = self.offers()
        self.assertEqual(set(offers), {"ok", "bowtie"})
        self.assertEqual((data_import.line_numbers, data_import.error_numbers), (17, 15))
        self.assertEqual(offers["bowtie"].geom.geom_type, "MultiPolygon")
        # Line number (from 1, in file order), id and reason.
        for error in (
            (3, "unknown-practice", 'unknown practice "Parapente"'),
            (5, "", "missing id"),
            (13, "double", "id given twice in the file"),
            (17, "uuid-taken", "uuid already used by an offer of another source"),
        ):
            self.assertIn(error, parser.errors)
        self.assertEqual(len(parser.errors), 15)

    def test_preview_writes_nothing(self):
        first = self.run_import(gpkg([line("a"), line("b")]))
        data_import = self.make_import(gpkg([line("a", name="A renamed"), line("c"), line("d", "unknown")]))
        preview = OfferParser(data_import).preview()
        self.assertEqual(preview, {"lines": 3, "created": 1, "updated": 1, "deleted": 1, "errors": 1})
        self.assertEqual(set(self.offers()), {"a", "b"})
        self.assertEqual(self.offers()["a"].name, "Offre a")
        self.assertEqual(Offer.objects.filter(data_import=data_import).count(), 0)
        self.assertEqual(first.offers.count(), 2)

    def test_deleting_an_import_deletes_the_offers_it_wrote_last(self):
        first = self.run_import(gpkg([line("a"), line("b")]))
        second = self.run_import(gpkg([line("a", name="A renamed"), line("b", "unknown"), line("c")]))
        # a updated and c created by the second import; b, in error, unchanged.
        self.assertEqual(
            {k: o.data_import for k, o in self.offers().items()},
            {"a": second, "b": first, "c": second},
        )
        first.delete()
        self.assertEqual(set(self.offers()), {"a", "c"})
        second.delete()
        self.assertEqual(self.offers(), {})

    def test_reimport_replaces_the_source_offers(self):
        first_uuid = uuid.uuid4()
        self.run_import(gpkg([line("a"), line("b"), line("c", uuid=str(first_uuid)), line("d")]))
        other = self.make_offer(source=DataSource.objects.get(code="visorando"), external_id="b")
        before = self.offers()

        data_import = self.run_import(
            gpkg(
                [
                    line("a", name="A renamed"),
                    # b no longer listed: deleted
                    line("c"),  # the file is the reference: uuid cleared
                    line("d", "unknown"),  # in error: kept unchanged
                    line("e"),
                ]
            )
        )
        offers = self.offers()
        self.assertEqual(data_import.error_numbers, 1)
        self.assertEqual(set(offers), {"a", "c", "d", "e"})
        self.assertEqual(offers["a"].name, "A renamed")
        self.assertEqual(offers["a"].pk, before["a"].pk)
        self.assertIsNone(offers["c"].uuid)
        self.assertEqual(offers["d"].practice.code, "hiking")
        self.assertTrue(Offer.objects.filter(pk=other.pk).exists())

    def test_rejected_files_change_nothing(self):
        self.run_import(gpkg([line("a")]))
        geojson = json.dumps({"type": "FeatureCollection", "features": []}).encode()
        for content, reason in (
            (b"not a file", "readable GeoPackage"),
            (geojson, "Only GeoPackage"),
            (gpkg([line("a")], other_layer=True), "single layer"),
            (gpkg([{k: v for k, v in line("a").items() if k != "practice"}]), "Missing columns: practice"),
            (gpkg([line("a")], crs=None), "coordinate reference system"),
            (gpkg([line("a", "unknown"), line("")]), "no valid line"),
        ):
            with self.subTest(reason), self.assertRaisesMessage(ValueError, reason):
                self.run_import(content)
            self.assertEqual(DataImport.objects.latest("pk").error_numbers, 1)
            self.assertEqual(set(self.offers()), {"a"})


class OfferImportAdminTests(OfferImportTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.org", "x"))
        self.url = reverse("admin:outdoor_offerimport_add")
        self.changelist = reverse("admin:outdoor_offerimport_changelist")

    def upload(self, content):
        return self.client.post(
            self.url, {"source": self.source.pk, "file": SimpleUploadedFile("offres.gpkg", content)}
        )

    def confirm(self, preview, *button):
        return self.client.post(self.url, {"token": preview.context["token"], **dict.fromkeys(button, "")}, follow=True)

    def messages(self, response):
        return [str(m) for m in response.context["messages"]]

    def stored_files(self):
        return [p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()]

    def test_add_page_shows_the_expected_columns(self):
        html = self.client.get(self.url).content.decode()
        for column in ("id", "name", "practice", "uuid"):
            self.assertIn(f"<code>{column}</code>", html)

    def test_preview_then_apply(self):
        self.run_import(gpkg([line("a"), line("gone")]))
        preview = self.upload(gpkg([line("a"), line("b"), line("c", "unknown")]))
        self.assertTemplateUsed(preview, "admin/outdoor/offerimport/preview.html")
        self.assertEqual(
            preview.context["preview"], {"lines": 3, "created": 1, "updated": 1, "deleted": 1, "errors": 1}
        )
        self.assertContains(preview, "unknown practice &quot;unknown&quot;")
        self.assertEqual(OfferImport.objects.count(), 1)  # only the first import
        self.assertEqual(set(self.offers()), {"a", "gone"})

        # No button name: import_loading.js disables the buttons on submit.
        response = self.confirm(preview)
        self.assertRedirects(response, self.changelist)
        self.assertEqual(
            self.messages(response),
            ['2 offer(s) imported, 1 line(s) in error: line 3 (c): unknown practice "unknown".'],
        )
        self.assertEqual(set(self.offers()), {"a", "b"})
        self.assertEqual(self.offers()["b"].data_import, OfferImport.objects.latest("pk"))

    def test_preview_then_cancel(self):
        response = self.confirm(self.upload(gpkg([line("a")])), "_cancel")
        self.assertRedirects(response, self.changelist)
        self.assertEqual(self.messages(response), ["Import cancelled."])
        self.assertFalse(OfferImport.objects.exists())
        self.assertEqual(self.offers(), {})
        self.assertEqual(self.stored_files(), [])

    def test_invalid_token(self):
        response = self.client.post(self.url, {"token": "forged"}, follow=True)
        self.assertEqual(self.messages(response), ["Preview expired or invalid: start the import again."])
        self.assertFalse(OfferImport.objects.exists())

    def test_rejected_file_is_kept_with_one_error(self):
        response = self.client.post(
            self.url, {"source": self.source.pk, "file": SimpleUploadedFile("offres.gpkg", b"not a file")}, follow=True
        )
        self.assertRedirects(response, self.changelist)
        [message] = self.messages(response)
        self.assertIn("Import rejected", message)
        self.assertEqual(OfferImport.objects.get().error_numbers, 1)
        self.assertEqual(len(self.stored_files()), 1)

    def test_view_page_of_an_import(self):
        data_import = self.run_import(gpkg([line("a")]))
        response = self.client.get(reverse("admin:outdoor_offerimport_change", args=[data_import.pk]))
        self.assertEqual(response.status_code, 200)

    def test_traffic_sources_are_left_out(self):
        sources = self.client.get(self.url).context["adminform"].form.fields["source"].queryset
        self.assertIn(self.source, sources)
        self.assertNotIn(DataSource.objects.get(code="outdoorvision"), sources)


class OfferAdminTests(OutdoorTestCase):
    def test_view_page_shows_a_map_instead_of_wkt(self):
        offer = self.make_offer(name="Lac")
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.org", "x"))
        html = self.client.get(reverse("admin:outdoor_offer_change", args=[offer.pk])).content.decode()
        self.assertIn('class="dj_map_wrapper"', html)
        self.assertNotIn("SRID=4326", html)
        # read_only_map.js patches MapWidget: it must come after OLMapWidget.js.
        self.assertIn('"read_only": true', html)
        self.assertLess(html.index("gis/js/OLMapWidget.js"), html.index("outdoor/read_only_map.js"))
