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
from .parsers.gbif import GBIFParser
from .parsers.sinp import SINPParser


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

class SINPParserTests(BiodiversityTestCase):
    HEADER = "id_perm_sinp;cd_ref;cd_nom;nom_valide;nom_cite;date_debut;date_fin;wkt_4326;precision;jdd_uuid"
    LYNX = str(uuid.uuid4())
    FROG = str(uuid.uuid4())
    DATASET = str(uuid.uuid4())

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))

    def line(
        self,
        uid,
        name="Lynx lynx (Linnaeus, 1758)",
        start="2025-05-11T08:00:00",
        geom="POINT(6.5 44.85)",
        precision="50",
    ):
        return f'"{uid}";"60612";"60612";"{name}";"Lynx";"{start}";"2025-05-12T00:00:00";"{geom}";"{precision}";"{self.DATASET}"'

    def run_import(self, *lines, header=HEADER):
        content = "\r\n".join([header, *lines]).encode()
        data_import = DataImport(source=DataSource.objects.get(code="geonature"))
        data_import.file.save("synthese.csv", ContentFile(content))
        return data_import, SINPParser(data_import).import_data()

    def test_one_record_per_line(self):
        polygon = "POLYGON((6.4 44.9, 6.5 44.9, 6.5 45, 6.4 44.9))"
        data_import, count = self.run_import(
            self.line(self.LYNX), self.line(self.FROG, geom=polygon, precision="")
        )
        self.assertEqual((count, data_import.line_numbers), (2, 2))
        lynx = TaxonRecord.objects.get(uuid=self.LYNX)
        self.assertEqual(
            (lynx.cd_ref, lynx.original_id_taxon, lynx.referential.code),
            (60612, "60612", "taxref"),
        )
        self.assertEqual(
            (lynx.record_start_date, lynx.record_end_date),
            (date(2025, 5, 11), date(2025, 5, 12)),
        )
        self.assertEqual(
            (lynx.coordinate_uncertainty_in_meters, str(lynx.dataset_uuid)),
            (50, self.DATASET),
        )
        self.assertEqual(lynx.source.code, "geonature")
        frog = TaxonRecord.objects.get(uuid=self.FROG)
        self.assertEqual(
            (frog.geom.geom_type, frog.coordinate_uncertainty_in_meters),
            ("Polygon", None),
        )

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


class GBIFParserTests(BiodiversityTestCase):
    HEADER = (
        "gbifID\tdatasetKey\tkingdom\tphylum\tclass\torder\tfamily\tgenus\tspecies\tinfraspecificEpithet\t"
        "taxonRank\tscientificName\ttaxonKey\tdecimalLatitude\tdecimalLongitude\tcoordinateUncertaintyInMeters\teventDate"
    )
    DATASET = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
    # pour éviter de monter toute la table taxref dans les tests CI. A voir si utile ?
    TAXREF = [  # (cd_nom, cd_ref, regne, lb_nom, nom_complet)
        (60612, 60612, "Animalia", "Lynx lynx", "Lynx lynx (Linnaeus, 1758)"),
        (61000, 60612, "Animalia", "Felis lynx", "Felis lynx Linnaeus, 1758"),
        (
            1001,
            1001,
            "Plantae",
            "Mentha aquatica subsp. aquatica",
            "Mentha aquatica subsp. aquatica",
        ),
        (
            2001,
            2001,
            "Animalia",
            "Oryctes nasicornis corniculatus",
            "Oryctes nasicornis corniculatus Villa, 1833",
        ),
        (3001, 3001, "Plantae", "Asteraceae", "Asteraceae Bercht. & J.Presl"),
        (4001, 4001, "Plantae", "Bellis perennis", "Bellis perennis L."),
        (4002, 4002, "Plantae", "Bellis perennis", "Bellis perennis Mill."),  # homonym
    ]

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))
        with connection.cursor() as cursor:
            cursor.execute("create schema taxonomie")
            cursor.execute(
                "create table taxonomie.taxref (cd_nom int, cd_ref int, regne text, lb_nom text, nom_complet text)"
            )
            cursor.executemany(
                "insert into taxonomie.taxref values (%s, %s, %s, %s, %s)", self.TAXREF
            )

    def line(
        self,
        gbif_id,
        name="Lynx lynx (Linnaeus, 1758)",
        key="7SBMG",
        rank="SPECIES",
        species="Lynx lynx",
        epithet="",
        kingdom="Animalia",
        family="",
        event_date="2026-06-26T13:41",
        uncertainty="4.0",
    ):
        return "\t".join(
            [
                str(gbif_id),
                self.DATASET,
                kingdom,
                "",
                "",
                "",
                family,
                "",
                species,
                epithet,
                rank,
                name,
                key,
                "44.85",
                "6.5",
                uncertainty,
                event_date,
            ]
        )

    def run_import(self, *lines, header=HEADER):
        content = "\n".join([header, *lines]).encode()
        data_import = DataImport(source=DataSource.objects.get(code="gbif"))
        data_import.file.save("occurrence.txt", ContentFile(content))
        return data_import, GBIFParser(data_import).import_data()

    def record(self, gbif_id):
        return TaxonRecord.objects.get(
            uuid=uuid.uuid5(
                uuid.NAMESPACE_URL, f"https://www.gbif.org/occurrence/{gbif_id}"
            )
        )

    def test_one_record_per_line(self):
        data_import, count = self.run_import(
            self.line(1), self.line(2, event_date="1869-05-23/1870-08")
        )
        self.assertEqual(
            (count, data_import.line_numbers, data_import.error_numbers), (2, 2, 0)
        )
        lynx = self.record(1)
        self.assertEqual(
            (lynx.cd_ref, lynx.original_id_taxon, lynx.referential.code),
            (60612, "7SBMG", "col"),
        )
        self.assertEqual(
            (lynx.record_start_date, lynx.record_end_date),
            (date(2026, 6, 26), date(2026, 6, 26)),
        )
        self.assertEqual(
            (lynx.geom.x, lynx.geom.y, lynx.coordinate_uncertainty_in_meters),
            (6.5, 44.85, 4),
        )
        self.assertEqual(
            (str(lynx.dataset_uuid), lynx.source.code), (self.DATASET, "gbif")
        )
        old = self.record(2)
        self.assertEqual(
            (old.record_start_date, old.record_end_date),
            (date(1869, 5, 23), date(1870, 8, 31)),
        )

    def test_cd_ref_matching(self):
        self.run_import(
            self.line(
                1, name="Felis lynx Linnaeus, 1758", key="111"
            ),  # synonym, full name
            self.line(
                2, name="Lynx lynx Linnaeus 1758", key="222"
            ),  # other authorship: species name
            self.line(
                3,
                name="Mentha aquatica var. aquatica",
                key="333",
                rank="SUBSPECIES",
                species="Mentha aquatica",
                epithet="aquatica",
                kingdom="Plantae",
            ),
            self.line(
                4,
                name="Oryctes nasicornis corniculatus",
                key="444",
                rank="SUBSPECIES",
                species="Oryctes nasicornis",
                epithet="corniculatus",
            ),
            self.line(
                5,
                name="Asteraceae",
                key="555",
                rank="FAMILY",
                species="",
                family="Asteraceae",
                kingdom="Plantae",
            ),
            self.line(
                6,
                name="Bellis perennis",
                key="666",
                species="Bellis perennis",
                kingdom="Plantae",
            ),  # ambiguous
            self.line(
                7, name="Lynx lynx", key="777", kingdom="Plantae"
            ),  # other kingdom
            self.line(8, name="Mystery mystery", key="888", species="Mystery mystery"),
        )
        self.assertEqual(
            [self.record(i).cd_ref for i in range(1, 9)],
            [60612, 60612, 1001, 2001, 3001, None, None, None],
        )
        self.assertEqual(self.record(1).referential.code, "gbif")

    def test_lines_without_valid_date_are_errors(self):
        data_import, count = self.run_import(
            self.line(1),
            self.line(2, event_date=""),
            self.line(3, event_date="2026-13"),
        )
        self.assertEqual(
            (count, data_import.line_numbers, data_import.error_numbers), (1, 3, 2)
        )

    def test_semicolon_csv_is_read(self):
        lines = [self.HEADER, self.line(1, uncertainty="")]
        content = "\n".join(line.replace("\t", ";") for line in lines).encode()
        data_import = DataImport(source=DataSource.objects.get(code="gbif"))
        data_import.file.save("export.csv", ContentFile(content))
        self.assertEqual(GBIFParser(data_import).import_data(), 1)
        self.assertIsNone(self.record(1).coordinate_uncertainty_in_meters)

    def test_reimport_does_not_duplicate(self):
        self.run_import(self.line(1))
        self.run_import(self.line(1))
        self.assertEqual(TaxonRecord.objects.count(), 1)

    def test_missing_taxref_is_reported(self):
        with connection.cursor() as cursor:
            cursor.execute("drop schema taxonomie cascade")
        with self.assertRaisesMessage(ValueError, "TaxRef n'est pas chargé"):
            self.run_import(self.line(1))
