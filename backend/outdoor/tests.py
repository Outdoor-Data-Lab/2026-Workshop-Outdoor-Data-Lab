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
        response = self.client.get(self.url, {'area': self.paris.area_code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        external_ids = {r['external_id'] for r in response.data['results']}
        self.assertEqual(external_ids, {'paris_001', 'paris_002'})

    def test_filter_by_nonexistent_area(self):
        """Test filtering by non-existent area returns 400 error."""
        response = self.client.get(self.url, {'area': 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('area', response.data)

    def test_combined_filter_area_and_practice(self):
        """Test combining area and practice filters."""
        response = self.client.get(self.url, {
            'area': self.paris.area_code,
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
            'area': self.paris.area_code,
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

    def test_list_without_type_filter_no_offers_count(self):
        """Test that listing without type_code filter does not include offers_count."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if response.data['results']:
            result = response.data['results'][0]
            # Should not have offers_count when not filtered by type_code
            self.assertNotIn('offers_count', result)

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