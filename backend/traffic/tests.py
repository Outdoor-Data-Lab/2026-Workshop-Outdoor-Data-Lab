from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum
from django.db.models import ProtectedError
from django.test import Client, SimpleTestCase, TestCase

from commons.models import DataSource, Practice
from workshop2026.processing.score import BasicFrequentationScore, CazalisFrequentationScore

from .models import CountingMeasure, CountingObject, CountingObjectType, Unit


def dt(day, hour=0):
    return datetime(2026, 7, day, hour, tzinfo=timezone.utc)


class TrafficTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Seeded by commons 0002 and traffic 0002.
        cls.source = DataSource.objects.get(code="outdoorvision")
        cls.type = CountingObjectType.objects.get(code="counter")
        cls.person = Unit.objects.get(code="person")

    def make_object(self, **kwargs):
        return CountingObject.objects.create(
            type=self.type,
            source=self.source,
            geom=Point(6.4, 44.9, srid=4326),
            **kwargs,
        )


class SchemaTests(TrafficTestCase):
    def test_tables_are_in_traffic_schema(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "select tablename from pg_tables where schemaname = 'traffic'"
            )
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(
            tables,
            {
                "counting_object_types",
                "counting_objects",
                "counting_measures",
                "units",
            },
        )


class CountingObjectTests(TrafficTestCase):
    def test_data_range_is_computed_from_measures(self):
        obj = self.make_object()
        self.assertIsNone(CountingObject.objects.with_data_range().get().first_data)
        for day in (15, 16, 17):
            CountingMeasure.objects.create(
                counting_object=obj,
                start_datetime=dt(day),
                end_datetime=dt(day) + timedelta(days=1),
                count=10,
                unit=self.person,
            )
        obj = CountingObject.objects.with_data_range().get()
        self.assertEqual(obj.first_data, dt(15))
        self.assertEqual(obj.latest_data, dt(18))

    def test_external_id_unique_per_source(self):
        self.make_object(external_id="42")
        with self.assertRaises(IntegrityError):
            self.make_object(external_id="42")

    def test_same_segment_from_several_origins(self):
        garmin = DataSource.objects.get(code="garmin")
        komoot = DataSource.objects.get(code="komoot")
        self.make_object(external_id="segment-1", origin=garmin)
        self.make_object(external_id="segment-1", origin=komoot)
        with self.assertRaises(IntegrityError):
            self.make_object(external_id="segment-1", origin=garmin)

    def test_empty_origin_counts_for_uniqueness(self):
        self.make_object(external_id="42", origin=None)
        with self.assertRaises(IntegrityError):
            self.make_object(external_id="42", origin=None)

    def test_objects_without_external_id_are_not_unique(self):
        self.make_object()
        self.make_object()
        self.assertEqual(CountingObject.objects.count(), 2)


class CountingMeasureTests(TrafficTestCase):
    def setUp(self):
        self.obj = self.make_object()

    def measure(self, **kwargs):
        values = {
            "start_datetime": dt(15, 10),
            "end_datetime": dt(15, 11),
            "count": 1,
            "unit": self.person,
        }
        return CountingMeasure.objects.create(
            counting_object=self.obj, **(values | kwargs)
        )

    def test_end_must_follow_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.measure(end_datetime=dt(15, 10))

    def test_practice_is_optional(self):
        self.assertIsNone(self.measure().practice)

    def test_measure_may_point_to_any_practice_level(self):
        self.measure(practice=Practice.objects.get(code="walking"))
        self.measure(practice=Practice.objects.get(code="mountain_biking"))
        self.assertEqual(CountingMeasure.objects.filter(practice__isnull=False).count(), 2)

    def test_unit_and_practice_in_use_are_protected(self):
        self.measure(practice=Practice.objects.get(code="hiking"))
        with self.assertRaises(ProtectedError):
            self.person.delete()
        with self.assertRaises(ProtectedError):
            Practice.objects.get(code="hiking").delete()


class CountingObjectApiTests(TrafficTestCase):
    def test_search_works_for_a_user_logged_in_to_the_admin(self):
        self.make_object()
        client = Client(enforce_csrf_checks=True)
        client.force_login(get_user_model().objects.create_user("user@example.org", "x"))
        square = [[6, 44], [7, 44], [7, 45], [6, 45], [6, 44]]
        response = client.post(
            "/api/traffic/counting-object/search",
            {"geometry": {"type": "Polygon", "coordinates": [square]}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)


class ReferenceDataTests(TestCase):
    def test_initial_units(self):
        self.assertEqual(
            set(Unit.objects.values_list("code", flat=True)),
            {"person", "tent", "bike", "vehicle", "animal"},
        )

    def test_initial_counting_object_types(self):
        self.assertEqual(
            set(CountingObjectType.objects.values_list("code", flat=True)),
            {"counter", "segment"},
        )


class BasicFrequentationScoreTests(SimpleTestCase):
    @patch("workshop2026.processing.score.MaterializedViewCount.objects.filter")
    def test_compute_sums_counts_from_all_sources_per_area(self, filter_counts):
        filter_counts.return_value.values.return_value.annotate.return_value = [
            {"id_area": 12, "total": 25},
            {"id_area": 13, "total": 8},
        ]
        score_grid = BasicFrequentationScore.compute(geom_ids=[12, 13])

        filter_counts.assert_called_once_with(id_area__in=[12, 13])
        filter_counts.return_value.values.assert_called_once_with("id_area")
        filter_counts.return_value.values.return_value.annotate.assert_called_once_with(
            total=Sum("counts")
        )
        self.assertEqual(score_grid, {12: 25, 13: 8})

    @patch("workshop2026.processing.score.MaterializedViewCount.objects.filter")
    @patch("workshop2026.processing.score.LArea.objects.filter")
    def test_compute_includes_ids_from_geometry_and_geom_ids(
        self, filter_areas, filter_counts
    ):
        filter_areas.return_value.values_list.return_value = [13, 14]
        filter_counts.return_value.values.return_value.annotate.return_value = [
            {"id_area": 12, "total": 25},
            {"id_area": 13, "total": 8},
            {"id_area": 14, "total": 4},
        ]

        score_grid = BasicFrequentationScore.compute(
            geoms=Point(6.4, 44.9, srid=4326),
            geom_ids=[12, 13],
        )

        filter_areas.assert_called_once()
        self.assertEqual(filter_areas.call_args.kwargs["geom__intersects"].srid, 2154)
        filter_counts.assert_called_once_with(id_area__in=[12, 13, 14])
        self.assertEqual(score_grid, {12: 25, 13: 8, 14: 4})


class CazalisFrequentationScoreTests(SimpleTestCase):
    @patch("workshop2026.processing.score.MaterializedViewCount.objects.filter")
    def test_compute_applies_source_weights_per_area(self, filter_counts):
        filter_counts.return_value.values.return_value = [
            {"id_area": 12, "id_source": 1, "counts": 10},
            {"id_area": 12, "id_source": 2, "counts": 5},
            {"id_area": 13, "id_source": 1, "counts": 4},
            {"id_area": 13, "id_source": 2, "counts": 3},
        ]

        score_grid = CazalisFrequentationScore.compute(
            geom_ids=[12, 13],
            source_weights={1: 2, 2: 3},
        )

        filter_counts.assert_called_once_with(id_area__in=[12, 13])
        filter_counts.return_value.values.assert_called_once_with(
            "id_area", "id_source", "counts"
        )
        self.assertEqual(score_grid, {12: 35, 13: 17})

    @patch("workshop2026.processing.score.MaterializedViewCount.objects.filter")
    def test_compute_rejects_missing_source_weight(self, filter_counts):
        filter_counts.return_value.values.return_value = [
            {"id_area": 12, "id_source": 3, "counts": 10},
        ]

        with self.assertRaisesRegex(ValueError, "Missing weight for source ID 3"):
            CazalisFrequentationScore.compute(geom_ids=[12], source_weights={})
