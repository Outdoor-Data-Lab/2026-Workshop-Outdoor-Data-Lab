from django.contrib.gis.geos import LineString, Point
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.test import TestCase

from commons.models import DataSource, Practice

from .models import Offer


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
