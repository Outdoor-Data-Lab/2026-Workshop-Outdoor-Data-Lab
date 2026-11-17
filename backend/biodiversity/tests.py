from datetime import date

from django.contrib.gis.geos import Point
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from commons.models import DataSource

from .models import HabitatRecord, HabitatStation, TaxonomicReferential, TaxonRecord


class BiodiversityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Seeded by commons migration 0002 and biodiversity migration 0002.
        cls.source = DataSource.objects.get(code="gbif")
        cls.taxref = TaxonomicReferential.objects.get(code="taxref")

    def make_record(self, **kwargs):
        values = {
            "source": self.source,
            "cd_ref": 60612,
            "original_id_taxon": "60612",
            "referential": self.taxref,
            "scientific_name": "Lynx lynx (Linnaeus, 1758)",
            "record_start_date": date(2026, 7, 15),
            "record_end_date": date(2026, 7, 15),
            "geom": Point(6.4, 44.9, srid=4326),
        }
        return TaxonRecord.objects.create(**(values | kwargs))


class SchemaTests(BiodiversityTestCase):
    def test_tables_are_in_biodiversity_schema(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "select tablename from pg_tables where schemaname = 'biodiversity'"
            )
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(
            tables,
            {
                "taxonomic_referentials",
                "taxon_records",
                "habitat_stations",
                "habitat_records",
            },
        )


class TaxonRecordTests(BiodiversityTestCase):
    def test_end_date_cannot_precede_start_date(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_record(record_end_date=date(2026, 7, 14))

    def test_cd_ref_is_optional(self):
        record = self.make_record(
            cd_ref=None,
            original_id_taxon="2435099",
            referential=TaxonomicReferential.objects.get(code="gbif"),
        )
        self.assertIsNone(record.cd_ref)

    def test_uuid_is_unique(self):
        record = self.make_record()
        with self.assertRaises(IntegrityError):
            self.make_record(uuid=record.uuid)

    def test_referential_in_use_is_protected(self):
        self.make_record()
        with self.assertRaises(ProtectedError):
            self.taxref.delete()


class HabitatTests(BiodiversityTestCase):
    def test_records_are_deleted_with_their_station(self):
        station = HabitatStation.objects.create(
            source=self.source, geom=Point(6.4, 44.9, srid=4326)
        )
        HabitatRecord.objects.create(station=station, cd_hab=1234)
        HabitatRecord.objects.create(
            station=station, cd_hab=5678, community_interest=True
        )
        self.assertEqual(station.habitat_records.count(), 2)
        station.delete()
        self.assertFalse(HabitatRecord.objects.exists())


class ReferenceDataTests(TestCase):
    def test_initial_taxonomic_referentials(self):
        self.assertEqual(
            set(TaxonomicReferential.objects.values_list("code", flat=True)),
            {"taxref", "gbif", "col", "worms"},
        )
