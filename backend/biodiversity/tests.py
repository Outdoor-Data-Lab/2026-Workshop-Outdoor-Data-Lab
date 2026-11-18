import tempfile
import uuid
from datetime import date
from pathlib import Path

from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings

from commons.models import DataImport, DataSource

from .models import HabitatRecord, HabitatStation, TaxonomicReferential, TaxonRecord
from .parsers.inpn import INPNParser


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


class INPNParserTests(BiodiversityTestCase):
    HEADER = "id_perm_sinp;cd_ref;cd_nom;nom_valide;nom_cite;date_debut;date_fin;wkt_4326;precision;jdd_uuid"
    LYNX = str(uuid.uuid4())
    FROG = str(uuid.uuid4())
    DATASET = str(uuid.uuid4())

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))

    def line(self, uid, name="Lynx lynx (Linnaeus, 1758)", start="2025-05-11T08:00:00", geom="POINT(6.5 44.85)", precision="50"):
        return f'"{uid}";"60612";"60612";"{name}";"Lynx";"{start}";"2025-05-12T00:00:00";"{geom}";"{precision}";"{self.DATASET}"'

    def run_import(self, *lines, header=HEADER):
        content = "\r\n".join([header, *lines]).encode()
        data_import = DataImport(source=DataSource.objects.get(code="geonature"))
        data_import.file.save("synthese.csv", ContentFile(content))
        return data_import, INPNParser(data_import).import_data()

    def test_one_record_per_line(self):
        polygon = "POLYGON((6.4 44.9, 6.5 44.9, 6.5 45, 6.4 44.9))"
        data_import, count = self.run_import(self.line(self.LYNX), self.line(self.FROG, geom=polygon, precision=""))
        self.assertEqual((count, data_import.line_numbers), (2, 2))
        lynx = TaxonRecord.objects.get(uuid=self.LYNX)
        self.assertEqual((lynx.cd_ref, lynx.original_id_taxon, lynx.referential.code), (60612, "60612", "taxref"))
        self.assertEqual((lynx.record_start_date, lynx.record_end_date), (date(2025, 5, 11), date(2025, 5, 12)))
        self.assertEqual((lynx.coordinate_uncertainty_in_meters, str(lynx.dataset_uuid)), (50, self.DATASET))
        self.assertEqual(lynx.source.code, "geonature")
        frog = TaxonRecord.objects.get(uuid=self.FROG)
        self.assertEqual((frog.geom.geom_type, frog.coordinate_uncertainty_in_meters), ("Polygon", None))

    def test_reimport_updates_records(self):
        self.run_import(self.line(self.LYNX))
        self.run_import(self.line(self.LYNX, name="Lynx lynx"))
        self.assertEqual(TaxonRecord.objects.get().scientific_name, "Lynx lynx")

    def test_incomplete_line_imports_nothing(self):
        with self.assertRaisesMessage(ValueError, "lignes 3"):
            self.run_import(self.line(self.LYNX), self.line(self.FROG, start=""))
        self.assertFalse(TaxonRecord.objects.exists())

    def test_missing_column_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "manquantes : wkt_4326"):
            self.run_import(header=self.HEADER.replace("wkt_4326", "geom"))
