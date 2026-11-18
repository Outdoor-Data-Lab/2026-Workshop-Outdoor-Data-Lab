import json
import tempfile
import uuid
from datetime import datetime, timedelta
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
from rest_framework import status
from rest_framework.test import APIClient

from commons.models import DataImport, DataSource, Practice
from ref_geo.tests import RefGeoTestCase

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
class OfferAPITestCase(TestCase):
    """Test cases for Offer API endpoints."""

    @classmethod
    def setUpTestData(cls):
        """Create test data fixtures."""
        # Create practices
        cls.practice_hiking = Practice.objects.get(
            code='hiking',
        )
        cls.practice_climbing = Practice.objects.get(
            code='climbing',
        )

        # Create data sources
        cls.source_outdoorvision = DataSource.objects.get(
            code='outdoorvision',
        )
        cls.source_komoot = DataSource.objects.get(
            code='komoot',
        )

        # Create test offers
        cls.offer1 = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='trail_001',
            geom='POINT(2.3522 48.8566)',  # Paris
            practice=cls.practice_hiking,
            source=cls.source_outdoorvision
        )

        cls.offer2 = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='trail_002',
            geom='POINT(2.3522 48.8566)',
            practice=cls.practice_hiking,
            source=cls.source_komoot
        )

        cls.offer3 = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='climb_001',
            geom='POINT(5.7245 45.1885)',  # Grenoble
            practice=cls.practice_climbing,
            source=cls.source_outdoorvision
        )

        cls.offer4 = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='',  # Offer without external_id
            geom='POINT(0.0 0.0)',
            practice=cls.practice_climbing,
            source=cls.source_komoot
        )

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.url = reverse('offer-list')

    def test_response_includes_all_fields(self):
        """Test that response includes all fields."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data['results'][0]

        required_fields = [
            'id', 'uuid', 'external_id', 'practice', 'practice_label',
            'source', 'source_label', 'date_create', 'date_update', 'geom',
            "practice_label", "source_label"
        ]
        for field in required_fields:
            self.assertIn(field, result)

    def test_filter_by_practice(self):
        """Test filtering offers by practice."""
        response = self.client.get(self.url, {'practice': self.practice_hiking.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        for result in response.data['results']:
            self.assertEqual(result['practice'], self.practice_hiking.id)

    def test_filter_by_source(self):
        """Test filtering offers by source."""
        response = self.client.get(self.url, {'source': self.source_outdoorvision.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        for result in response.data['results']:
            self.assertEqual(result['source'], self.source_outdoorvision.id)

    def test_filter_by_uuid(self):
        """Test filtering offers by exact UUID."""
        response = self.client.get(self.url, {'uuid': str(self.offer1.uuid)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['uuid'], str(self.offer1.uuid))

    def test_filter_by_uuid_invalid(self):
        """Test filtering with an invalid UUID returns no results."""
        response = self.client.get(self.url, {'uuid': str(uuid.uuid4())})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_filter_by_external_id_exact(self):
        """Test filtering offers by exact external_id."""
        response = self.client.get(self.url, {'external_id': 'climb_001'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['external_id'], 'climb_001')

    def test_filter_by_date_range(self):
        """Test filtering offers by date range."""
        now = datetime.now()
        future_date = (now + timedelta(days=1)).isoformat()
        past_date = (now - timedelta(days=1)).isoformat()

        # All offers created within the past day
        response = self.client.get(self.url, {'date_from': past_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)

        # No offers created in the future
        response = self.client.get(self.url, {'date_to': future_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)

    def test_combined_filters(self):
        """Test combining multiple filters."""
        response = self.client.get(self.url, {
            'practice': self.practice_hiking.id,
            'source': self.source_outdoorvision.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.offer1.id)

    def test_retrieve_single_offer(self):
        """Test retrieving a single offer by ID."""
        url = reverse('offer-detail', kwargs={'pk': self.offer1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.offer1.id)
        self.assertEqual(response.data['external_id'], 'trail_001')


class OfferGeoFilterTests(RefGeoTestCase):
    """Test cases for geographic filtering of Offer API endpoints.

    Inherits from RefGeoTestCase to reuse ref_geo test data (paris and chamonix areas).
    """

    @classmethod
    def setUpTestData(cls):
        """Set up ref_geo test data, then create offers within those areas."""
        # Setup ref_geo schema and test data (paris, chamonix areas, etc.)
        super().setUpTestData()

        # Create practices and sources
        cls.practice_hiking = Practice.objects.get(code='hiking')
        cls.source_outdoorvision = DataSource.objects.get(code='outdoorvision')

        # Create offers within Paris area (2.2, 48.8, 2.5, 48.9)
        cls.offer_paris1 = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='paris_001',
            geom='POINT(2.3522 48.8566)',  # Paris center
            practice=cls.practice_hiking,
            source=cls.source_outdoorvision
        )

        cls.offer_paris2 = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='paris_002',
            geom='POINT(2.3505 48.8551)',  # Paris center, slightly different
            practice=cls.practice_hiking,
            source=cls.source_outdoorvision
        )

        # Create offer within Chamonix area (6.8, 45.9, 6.9, 46.0)
        cls.offer_chamonix = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='chamonix_001',
            geom='POINT(6.8696 45.92)',  # Chamonix center
            practice=cls.practice_hiking,
            source=cls.source_outdoorvision
        )

        # Create offer outside both areas
        cls.offer_lyon = Offer.objects.create(
            uuid=uuid.uuid4(),
            external_id='lyon_001',
            geom='POINT(4.8357 45.7640)',  # Lyon
            practice=cls.practice_hiking,
            source=cls.source_outdoorvision
        )

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.url = reverse('offer-list')

    def test_filter_by_area_returns_offers_in_area(self):
        """Test filtering offers by area returns only offers within that area."""
        response = self.client.get(self.url, {'area_code': self.paris.area_code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        external_ids = {r['external_id'] for r in response.data['results']}
        self.assertEqual(external_ids, {'paris_001', 'paris_002'})

    def test_filter_by_nonexistent_area(self):
        """Test filtering by non-existent area returns 400 error."""
        response = self.client.get(self.url, {'area_code': 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('area_code', response.data)

    def test_combined_filter_area_and_practice(self):
        """Test combining area and practice filters."""
        response = self.client.get(self.url, {
            'area_code': self.paris.area_code,
            'practice': self.practice_hiking.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_json_format_response(self):
        """Test JSON format response (default)."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('count', data)
        # Check that results include geom field in JSON format
        if data['results']:
            self.assertIn('geom', data['results'][0])

    def test_geojson_feature_properties(self):
        """Test that GeoJSON features include correct properties."""
        response = self.client.get(self.url, {
            'area_code': self.paris.area_code,
            'format': 'geojson'
        })
        data = response.json()
        feature = data['features'][0]
        properties = feature['properties']
        self.assertIn('id', feature)
        self.assertIn('geometry', feature)

        fields = ['uuid', 'external_id', 'practice', 'practice_label', 'source', 'source_label']
        for field in fields:
            self.assertIn(field, properties)


class LAreaAPITestCase(RefGeoTestCase):
    """Tests de l'endpoint LAreaViewSet (réutilise les zones paris / chamonix de RefGeoTestCase)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.practice = Practice.objects.get(code='hiking')
        source = DataSource.objects.get(code='outdoorvision')

        # 2 offres dans Paris, 1 dans Chamonix
        for ext_id, wkt in [
            ('paris_001', 'POINT(2.3522 48.8566)'),
            ('paris_002', 'POINT(2.3505 48.8551)'),
            ('chamonix_001', 'POINT(6.8696 45.92)'),
        ]:
            Offer.objects.create(
                uuid=uuid.uuid4(), external_id=ext_id, geom=wkt,
                practice=cls.practice, source=source,
            )

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('offer_area-list')

    def test_list_areas(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        ids = {r['id_area'] for r in response.data['results']}
        self.assertIn(self.paris.id_area, ids)
        self.assertIn(self.chamonix.id_area, ids)

    def test_filter_by_type_code(self):
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {'type_code': type_code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_filter_by_bbox(self):
        response = self.client.get(self.url, {'bbox': '2.2,48.8,2.5,48.9'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {r['id_area'] for r in response.data['results']}
        self.assertIn(self.paris.id_area, ids)
        self.assertNotIn(self.chamonix.id_area, ids)

    def test_geojson_format(self):
        response = self.client.get(self.url, {'format': 'geojson'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertTrue(data['features'])
        self.assertIn('geometry', data['features'][0])

    def test_filter_by_type_code_with_offers_count(self):
        """Test filtering areas by type code returns offers count in each area."""
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {'type_code': type_code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

        # Check that the response includes offers_count for areas of the specified type
        paris_result = next(
            (r for r in response.data['results'] if r['id_area'] == self.paris.id_area),
            None
        )
        self.assertIsNotNone(paris_result)
        self.assertIn('offers_count', paris_result)
        self.assertEqual(paris_result['offers_count'], 2)

    def test_filter_by_type_code_includes_type_code_in_response(self):
        """Test that response includes type_code when filtering by type."""
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {'type_code': type_code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # All results should have the type_code field
        for result in response.data['results']:
            self.assertIn('type_code', result)
            self.assertEqual(result['type_code'], type_code)

    def test_filter_by_type_code_unknown_type(self):
        """Test filtering by unknown type code returns empty results."""
        response = self.client.get(self.url, {'type_code': 'UNKNOWN'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'], [])

    def test_filter_by_type_code_with_geojson(self):
        """Test filtering by type code with GeoJSON format."""
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {
            'type_code': type_code,
            'format': 'geojson'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['type'], 'FeatureCollection')

        if data['features']:
            properties = data['features'][0]['properties']
            self.assertIn('type_code', properties)
            self.assertIn('offers_count', properties)

    def test_filter_by_type_code_with_practice_count(self):
        """Test filtering areas by type code with practice count breakdown."""
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {
            'type_code': type_code,
            'practice_count': 'true'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        paris_result = next(r for r in response.data['results'] if r['id_area'] == self.paris.id_area)
        self.assertEqual(paris_result['offers_count'], 2)
        self.assertEqual(len(paris_result['offers_count_by_practice']), 1)
        self.assertEqual(paris_result['offers_count_by_practice'],
                         [{'practice_code': self.practice.code, 'practice_label': self.practice.label, 'count': 2}])

    def test_practice_count_without_practice_count_param(self):
        """Test that offers_count_by_practice is not included without practice_count=true."""
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {'type_code': type_code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        paris_result = next(r for r in response.data['results'] if r['id_area'] == self.paris.id_area)
        self.assertNotIn('offers_count_by_practice', paris_result)

    def test_practice_count_with_geojson(self):
        """Test practice count with GeoJSON format."""
        type_code = self.paris.type.type_code
        response = self.client.get(self.url, {
            'type_code': type_code,
            'practice_count': 'true',
            'format': 'geojson'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('offers_count_by_practice', data['features'][0]['properties'])


class DynamicFieldsTestCase(OfferAPITestCase):
    """Test cases for DynamicFieldsMixin functionality."""

    def test_dynamic_fields_basic_filtering(self):
        """Test that only requested fields are returned when using ?fields parameter."""
        response = self.client.get(self.url, {'fields': 'id,external_id,practice'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data['results'][0]

        # Should have requested fields
        self.assertIn('id', result)
        self.assertIn('external_id', result)
        self.assertIn('practice', result)

        # Should not have other fields
        self.assertNotIn('source', result)
        self.assertNotIn('date_create', result)
        self.assertNotIn('date_update', result)

    def test_dynamic_fields_with_whitespace(self):
        """Test that dynamic fields work correctly with whitespace in parameter."""
        response = self.client.get(self.url, {'fields': 'id, external_id , practice '})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data['results'][0]

        # Should have requested fields despite whitespace
        self.assertIn('id', result)
        self.assertIn('external_id', result)
        self.assertIn('practice', result)

    def test_dynamic_fields_excludes_unneeded_fields(self):
        """Test that unrequested fields are properly excluded."""
        response = self.client.get(self.url, {'fields': 'id,uuid'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data['results'][0]

        # Should only have requested fields
        self.assertEqual(set(result.keys()), {'id', 'uuid'})

    def test_dynamic_fields_no_filtering_without_parameter(self):
        """Test that all fields are returned when no fields parameter is provided."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data['results'][0]

        # Should have all fields
        required_fields = ['id', 'uuid', 'external_id', 'practice', 'practice_label',
                           'source', 'source_label', 'date_create', 'date_update', 'geom']
        for field in required_fields:
            self.assertIn(field, result)


# Offer imports and the offer admin (tests lost in #32, restored).


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
        return DataImport.objects.create(
            format="offers", source=self.source, file=SimpleUploadedFile("offres.gpkg", content)
        )

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
        self.assertEqual(preview, {"lines": 3, "rows": 2, "changes": {"Offers created": 1, "Offers updated": 1, "Offers deleted, missing from the file": 1}, "errors": 1})
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
            self.assertEqual(set(self.offers()), {"a"})


class OfferImportAdminTests(OfferImportTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(get_user_model().objects.create_superuser("admin@example.org", "x"))
        self.url = reverse("admin:outdoor_offerimport_add")
        self.changelist = reverse("admin:outdoor_offerimport_changelist")

    def upload(self, content):
        return self.client.post(
            self.url, {"format": "offers", "source": self.source.pk, "file": SimpleUploadedFile("offres.gpkg", content)}
        )

    def confirm(self, preview, *button):
        return self.client.post(self.url, {"token": preview.context["token"], **dict.fromkeys(button, "")}, follow=True)

    def messages(self, response):
        return [str(m) for m in response.context["messages"]]

    def stored_files(self):
        return [p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()]

    def test_add_page_shows_the_expected_file(self):
        # OfferParser.EXAMPLE, shown by import_example.js when a source is selected.
        self.assertContains(self.client.get(self.url), "Columns: id (the offer&#x27;s id in its source), name, practice")

    def test_preview_then_apply(self):
        self.run_import(gpkg([line("a"), line("gone")]))
        preview = self.upload(gpkg([line("a"), line("b"), line("c", "unknown")]))
        self.assertTemplateUsed(preview, "admin/commons/import_preview.html")
        self.assertEqual(preview.context["preview"], {"lines": 3, "rows": 2, "changes": {"Offers created": 1, "Offers updated": 1, "Offers deleted, missing from the file": 1}, "errors": 1})
        self.assertContains(preview, "unknown practice &quot;unknown&quot;")
        self.assertEqual(OfferImport.objects.count(), 1)  # only the first import
        self.assertEqual(set(self.offers()), {"a", "gone"})

        # No button name: import_loading.js disables the buttons on submit.
        response = self.confirm(preview)
        self.assertRedirects(response, self.changelist)
        self.assertEqual(self.messages(response), ["Import queued: its status and outcome are shown in the list."])
        # Run by the worker (at once in tests).
        self.assertEqual(
            OfferImport.objects.latest("pk").message,
            '2 item(s) imported, 1 line(s) in error: line 3 (c): unknown practice "unknown".',
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

    def test_rejected_file_keeps_nothing(self):
        response = self.client.post(
            self.url,
            {"format": "offers", "source": self.source.pk, "file": SimpleUploadedFile("offres.gpkg", b"not a file")},
            follow=True,
        )
        # Back to the form with the same format and source, and the reason.
        self.assertEqual(response.redirect_chain, [(f"{self.url}?format=offers&source={self.source.pk}", 302)])
        self.assertEqual(
            self.messages(response), ["Import refused, nothing was saved: The file is not a readable GeoPackage."]
        )
        self.assertFalse(OfferImport.objects.exists())
        self.assertEqual(self.stored_files(), [])

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
