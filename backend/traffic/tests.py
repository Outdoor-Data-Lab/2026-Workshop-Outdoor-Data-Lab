from datetime import datetime, timedelta, timezone

from django.contrib.gis.geos import Point
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from commons.models import DataSource, Practice

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
