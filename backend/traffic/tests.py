import io
import re
import tempfile
import zipfile
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
import shapely

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString, MultiPolygon, Point, Polygon
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import Client, SimpleTestCase, TestCase, override_settings

from commons.models import DataImport, DataSource, Practice
from ref_geo.models import BibAreasType, LArea
from workshop2026.processing.score import BasicFrequentationScore, CazalisFrequentationScore

from .models import (
    CountingMeasure,
    CountingObject,
    CountingObjectArea,
    CountingObjectType,
    Unit,
)
from .parsers.compteur import CompteurParser
from .parsers.inaturalist import INaturalistParser, observer_day_id
from .parsers.outdoorvision import OutdoorVisionParser
from .parsers.strava import StravaParser


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
        values = {
            "type": self.type,
            "source": self.source,
            "geom": Point(6.4, 44.9, srid=4326),
        }
        return CountingObject.objects.create(**(values | kwargs))


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
                "counting_object_areas",
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
        self.assertEqual(
            CountingMeasure.objects.filter(practice__isnull=False).count(), 2
        )

    def test_unit_and_practice_in_use_are_protected(self):
        self.measure(practice=Practice.objects.get(code="hiking"))
        with self.assertRaises(ProtectedError):
            self.person.delete()
        with self.assertRaises(ProtectedError):
            Practice.objects.get(code="hiking").delete()


class CountingObjectApiTests(TrafficTestCase):
    url = "/api/traffic/counting-objects"

    def setUp(self):
        self.garmin = DataSource.objects.get(code="garmin")
        self.inside = self.make_object(external_id="in", origin=self.garmin)
        self.make_object(external_id="out", geom=Point(-3.7, 40.4, srid=4326))

    def get(self, query=""):
        response = self.client.get(f"{self.url}?{query}")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_plain_json_with_relation_codes(self):
        data = self.get("ordering=id")
        self.assertEqual(data["count"], 2)
        first = data["results"][0]
        self.assertEqual(
            (first["type_code"], first["source_code"], first["origin_code"]),
            ("counter", "outdoorvision", "garmin"),
        )
        self.assertIsNone(data["results"][1]["origin_code"])
        self.assertNotIn("geom", first)

    def test_geojson(self):
        data = self.get("format=geojson")
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["features"][0]["geometry"]["type"], "Point")

    def test_spatial_and_code_filters(self):
        self.assertEqual(self.get("bbox=6,44,7,45")["count"], 1)
        self.assertEqual(self.get("point=6.4,44.9")["count"], 1)
        square = (
            '{"type": "Polygon", "coordinates": [[[6,44],[7,44],[7,45],[6,45],[6,44]]]}'
        )
        self.assertEqual(self.get(f"intersects={square}")["count"], 1)
        self.assertEqual(self.get("origin_code=garmin")["count"], 1)
        self.assertEqual(self.get("type_code=segment")["count"], 0)

    def test_measures_paginated_with_codes(self):
        for day in (15, 16, 17):
            CountingMeasure.objects.create(
                counting_object=self.inside,
                start_datetime=dt(day),
                end_datetime=dt(day) + timedelta(days=1),
                count=1,
                unit=self.person,
                practice=Practice.objects.get(code="hiking"),
            )
        response = self.client.get(
            "/api/traffic/counting-measures?limit=2&practice_code=hiking"
        )
        data = response.json()
        self.assertEqual((data["count"], len(data["results"])), (3, 2))
        self.assertEqual(data["results"][0]["unit_code"], "person")

    def test_dynamic_fields_filtering(self):
        """Test DynamicFieldsMixin filters fields correctly for all serializers in traffic.api.serializers."""
        # Test CountingObjectSerializer
        data = self.get("fields=id,uuid")
        result = data["results"][0]
        self.assertIn("id", result)
        self.assertIn("uuid", result)
        self.assertNotIn("external_id", result)
        self.assertNotIn("type_code", result)
        self.assertNotIn("source_code", result)
        # Verify only requested fields exist
        self.assertEqual(set(result.keys()), {"id", "uuid"})


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


class OutdoorVisionParserTests(TrafficTestCase):
    ROWS = [  # track 1 is split in two pieces, as in real exports.
        (1, "t1", "walking", "2025-07-01T08:00", "2025-07-01T09:00", [(6.40, 44.90), (6.41, 44.90)]),
        (2, "t1", "walking", "2025-07-01T09:30", "2025-07-01T11:00", [(6.42, 44.90), (6.43, 44.91)]),
        (3, "t2", "cycling", "2025-07-02T10:00", "2025-07-02T12:00", [(6.50, 44.80), (6.52, 44.81)]),
    ]

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))

    def run_import(self, rows=ROWS, drop=()):
        frame = gpd.GeoDataFrame(
            [
                dict(id=i, track_id=t, activity=a, date_start=f"{s}+02:00", date_end=f"{e}+02:00")
                for i, t, a, s, e, _ in rows
            ],
            geometry=[shapely.LineString(c) for *_, c in rows],
            crs=4326,
        ).drop(columns=list(drop))
        path = self.tmp / "export.gpkg"
        frame.to_file(path)
        data_import = DataImport(source=self.source)
        data_import.file.save("export.gpkg", ContentFile(path.read_bytes()))
        return data_import, OutdoorVisionParser(data_import).import_data()

    def test_one_object_and_one_passage_per_track(self):
        data_import, count = self.run_import()
        self.assertEqual((count, data_import.line_numbers), (2, 3))
        measure = CountingMeasure.objects.get(counting_object__external_id="t1")
        self.assertEqual((measure.count, measure.unit.code, measure.practice.code), (1, "person", "walking"))
        self.assertEqual(measure.start_datetime, datetime(2025, 7, 1, 6, tzinfo=timezone.utc))
        self.assertEqual(measure.end_datetime, datetime(2025, 7, 1, 9, tzinfo=timezone.utc))
        self.assertEqual(measure.counting_object.geom.num_geom, 2)  # both pieces kept
        self.assertEqual(CountingMeasure.objects.get(counting_object__external_id="t2").practice.code, "cycling")

    def test_reimport_does_not_duplicate(self):
        self.run_import()
        self.run_import()
        self.assertEqual((CountingObject.objects.count(), CountingMeasure.objects.count()), (2, 2))

    def test_unknown_activity_imports_nothing(self):
        with self.assertRaisesMessage(ValueError, "inconnues : swimming"):
            self.run_import([(1, "t1", "swimming", *self.ROWS[0][3:])])
        self.assertFalse(CountingObject.objects.exists())

    def test_missing_column_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "manquantes : track_id"):
            self.run_import(drop=["track_id"])

    def test_unreadable_file_is_rejected(self):
        data_import = DataImport(source=self.source)
        data_import.file.save("export.gpkg", ContentFile(b"not a GeoPackage"))
        with self.assertRaisesMessage(ValueError, "pas un GPKG lisible"):
            OutdoorVisionParser(data_import).import_data()


class StravaParserTests(TrafficTestCase):
    # Network of 3 edges; edge 30 is never used, like most of the Strava network.
    EDGES = {10: [(6.40, 44.90), (6.41, 44.90)], 20: [(6.41, 44.90), (6.42, 44.91)], 30: [(6.5, 44.8), (6.6, 44.8)]}

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))

    def run_import(self, year=2024, counts=((10, 80), (20, 15)), activity="Run,Walk,Hike", day=None, extra=()):
        """Import a zip of one export, plus the `extra` (name, content) files."""
        folder = Path(tempfile.mkdtemp(dir=self.tmp))
        gpd.GeoDataFrame(
            {"edgeUID": list(self.EDGES), "osmId": [1, 1, 2]},
            geometry=[shapely.LineString(c) for c in self.EDGES.values()],
            crs=4326,
        ).to_file(folder / "edges.shp")
        period = {"date": day} if day else {"year": year}  # daily or yearly export
        rows = [dict(edge_uid=e, activity_type=activity, total_trip_count=n, **period) for e, n in counts]
        pd.DataFrame(rows).to_csv(folder / "edges.csv", index=False)
        archive = folder.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w") as zip_file:
            for file in folder.iterdir():
                zip_file.write(file, file.name)
            for name, content in extra:
                zip_file.writestr(name, content)
        data_import = DataImport(source=DataSource.objects.get(code="strava"))
        data_import.file.save(archive.name, ContentFile(archive.read_bytes()))
        return data_import, StravaParser(data_import).import_data()

    def test_one_object_per_used_edge_and_one_yearly_measure(self):
        data_import, count = self.run_import()
        self.assertEqual((count, data_import.line_numbers), (2, 2))
        self.assertEqual(set(CountingObject.objects.values_list("external_id", flat=True)), {"10", "20"})
        measure = CountingMeasure.objects.get(counting_object__external_id="10")
        self.assertEqual((measure.count, measure.unit.code, measure.practice.code), (80, "person", "walking"))
        # Years are local: 1 January 00:00 in Paris = 31 December 23:00 UTC.
        self.assertEqual(measure.start_datetime, datetime(2023, 12, 31, 23, tzinfo=timezone.utc))
        self.assertEqual(measure.end_datetime, datetime(2024, 12, 31, 23, tzinfo=timezone.utc))
        self.assertEqual(measure.counting_object.type.code, "segment")

    def test_reimport_replaces_the_year(self):
        self.run_import()
        self.run_import(counts=((10, 90), (20, 20)))
        self.assertEqual(CountingObject.objects.count(), 2)
        self.assertEqual(sorted(CountingMeasure.objects.values_list("count", flat=True)), [20, 90])

    def test_new_year_reuses_edges(self):
        self.run_import(2024)
        self.run_import(2025, counts=((10, 100), (30, 5)))
        self.assertEqual(CountingObject.objects.count(), 3)
        self.assertEqual(CountingMeasure.objects.count(), 4)

    def test_daily_export_gives_one_measure_per_day(self):
        self.run_import(2024)
        self.run_import(counts=((10, 5), (20, 10)), day="2024-07-14")
        self.run_import(counts=((10, 5),), day="2024-07-15")
        daily = CountingMeasure.objects.get(counting_object__external_id="20", count=10)
        # 14 July 00:00 in Paris (summer time) = 13 July 22:00 UTC, for one day.
        self.assertEqual(daily.start_datetime, datetime(2024, 7, 13, 22, tzinfo=timezone.utc))
        self.assertEqual(daily.end_datetime, datetime(2024, 7, 14, 22, tzinfo=timezone.utc))
        # Daily imports keep the yearly measures of the same edges: 2 yearly + 3 daily.
        self.assertEqual((CountingObject.objects.count(), CountingMeasure.objects.count()), (2, 5))

    def test_yearly_import_keeps_daily_measures(self):
        self.run_import(counts=((10, 5), (20, 10)), day="2024-07-14")
        self.run_import(2024)
        self.assertEqual(CountingMeasure.objects.count(), 4)  # 2 daily + 2 yearly

    @patch.object(StravaParser, "PRACTICE_CODES", {"Run,Walk,Hike": "walking", "Ride": "cycling"})
    def test_other_activity_keeps_the_first_one(self):
        self.run_import(2024)
        self.run_import(2024, activity="Ride")
        practices = CountingMeasure.objects.values_list("practice__code", flat=True)
        self.assertEqual(sorted(practices), ["cycling", "cycling", "walking", "walking"])

    def test_duplicate_measures_are_refused(self):
        with self.assertRaisesMessage(ValueError, "Mesures Strava en double (même objet, période et pratique) : 1"):
            self.run_import(counts=((10, 80), (10, 5)))
        self.assertFalse(CountingObject.objects.exists())

    def test_archive_with_several_exports_is_refused(self):
        with self.assertRaisesMessage(ValueError,
                                      "un seul export, soit un .shp et un .csv (trouvé : 1 .shp et 2 .csv)"):
            self.run_import(extra=[("other.csv", "edge_uid,activity_type,year,total_trip_count\n")])
        with self.assertRaisesMessage(ValueError, "contient d'autres zips"):
            self.run_import(extra=[("all_edges_yearly_2023_is.zip", b"")])
        self.assertFalse(CountingObject.objects.exists())

    def test_unknown_activity_imports_nothing(self):
        with self.assertRaisesMessage(ValueError, "inconnues : Ride"):
            self.run_import(activity="Ride")
        self.assertFalse(CountingObject.objects.exists())


class CompteurParserTests(TrafficTestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))

    def run_import(self, counts=(("A", 5), ("A", 0), ("B", 3), ("B", 2))):
        # Two hours per counter, plus a counter at 0 all year and one without position.
        hours = ["2024-07-01 10:00:00", "2024-07-01 11:00:00"]
        rows = [(hours[i % 2], name, n, "POINT (6.4 44.9)") for i, (name, n) in enumerate(counts)]
        rows += [(h, "EMPTY", 0, "POINT (6.5 44.8)") for h in hours]
        rows += [(h, "NOWHERE", 7, None) for h in hours]
        csv = pd.DataFrame(rows, columns=["date_debut", "object_name", "count", "geom"]).assign(activity="hiking")
        data_import = DataImport(source=DataSource.objects.get(code="ecocompteur"))
        data_import.file.save("eco.csv", ContentFile(csv.to_csv(index=False).encode()))
        return data_import, CompteurParser(data_import).import_data()

    def test_one_counter_object_and_one_measure_per_hour(self):
        data_import, count = self.run_import()
        self.assertEqual((count, data_import.line_numbers, data_import.error_numbers), (4, 8, 4))
        self.assertEqual(set(CountingObject.objects.values_list("external_id", "type__code")),
                         {("A", "counter"), ("B", "counter")})
        measure = CountingMeasure.objects.get(counting_object__external_id="A", count=5)
        # 10:00 in Paris (summer time) = 08:00 UTC, measures last one hour.
        self.assertEqual(measure.start_datetime, datetime(2024, 7, 1, 8, tzinfo=timezone.utc))
        self.assertEqual(measure.end_datetime, datetime(2024, 7, 1, 9, tzinfo=timezone.utc))
        self.assertEqual(measure.practice.code, "hiking")
        self.assertTrue(CountingMeasure.objects.filter(counting_object__external_id="A", count=0).exists())

    def test_reimport_replaces_measures(self):
        self.run_import()
        self.run_import(counts=(("A", 9), ("A", 1), ("B", 3), ("B", 2)))
        self.assertEqual(CountingMeasure.objects.count(), 4)
        self.assertEqual(
            sorted(CountingMeasure.objects.filter(counting_object__external_id="A").values_list("count", flat=True)),
            [1, 9])


def zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class INaturalistParserTests(TrafficTestCase):
    # (observation id, observer name, login, day, latitude, longitude, obscured)
    OBSERVATIONS = [
        # The lines of an outing are not consecutive, as in real exports.
        (1, "Jeanne Martin", "jmartin", "2025-07-14", 44.90, 6.40, False),
        (2, "", "pdupont", "2025-07-14", 44.80, 6.50, False),  # no name: known by their login
        (3, "Jeanne Martin", "jmartin", "2025-07-14", 44.91, 6.41, False),  # same outing, second point
        (4, "Jeanne Martin", "jmartin", "2025-07-14", 44.91, 6.41, False),  # same point again
        (5, "Jeanne Martin", "jmartin", "2025-07-15", 44.92, 6.42, False),  # next day: another outing
        (6, "Ana Silva", "asilva", "2025-07-14", 44.85, 6.45, True),  # obscured: skipped
    ]

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(override_settings(MEDIA_ROOT=self.tmp / "media"))

    def import_file(self, name, content):
        data_import = DataImport(source=DataSource.objects.get(code="inaturalist"))
        data_import.file.save(name, ContentFile(content))
        return data_import, INaturalistParser(data_import).import_data()

    def inaturalist_export(self, observations=OBSERVATIONS):
        rows = [
            dict(id=i, observed_on=d, user_id=100 + i, user_login=login, user_name=name, latitude=lat, longitude=lon,
                 coordinates_obscured=str(obscured).lower(), scientific_name="Rupicapra rupicapra",
                 description="Vu\nau lac")
            for i, name, login, d, lat, lon, obscured in observations
        ]
        return zip_bytes(
            {"README.txt": "Export iNaturalist", "observations-1.csv": pd.DataFrame(rows).to_csv(index=False)})

    def gbif_download(self, observations):
        rows = [
            dict(gbifID=i, occurrenceID=f"https://www.inaturalist.org/observations/{i}", recordedBy=name or login,
                 eventDate=f"{d}T10:30", decimalLatitude=lat, decimalLongitude=lon,
                 coordinateUncertaintyInMeters=27285 if obscured else 10, species="Rupicapra rupicapra")
            for i, name, login, d, lat, lon, obscured in observations
        ]
        return zip_bytes({"0012597.csv": pd.DataFrame(rows).to_csv(index=False, sep="\t")})

    def test_one_passage_per_observer_and_day(self):
        data_import, count = self.run_export()
        self.assertEqual((count, data_import.line_numbers, data_import.error_numbers), (3, 6, 1))
        outing = CountingObject.objects.get(external_id=observer_day_id("Jeanne Martin", pd.Timestamp("2025-07-14")))
        self.assertEqual(outing.geom.num_geom, 2)  # her two places that day, the repeated point once
        measure = outing.measures.get()
        self.assertEqual((measure.count, measure.unit.code, measure.practice.code), (1, "person", "walking"))
        # 14 July in Paris (summer time) = 13 July 22:00 UTC, for one day.
        self.assertEqual(measure.start_datetime, datetime(2025, 7, 13, 22, tzinfo=timezone.utc))
        self.assertEqual(measure.end_datetime, datetime(2025, 7, 14, 22, tzinfo=timezone.utc))
        self.assertTrue(
            CountingObject.objects.filter(external_id=observer_day_id("pdupont", pd.Timestamp("2025-07-14"))))

    def test_observers_are_not_stored(self):
        self.run_export()
        for external_id in CountingObject.objects.values_list("external_id", flat=True):
            self.assertRegex(external_id, r"^[0-9a-f]{32}$")

    def test_gbif_after_the_export_counts_each_outing_once(self):
        self.run_export()
        new = (7, "Paul Roux", "proux", "2025-07-16", 44.95, 6.30, False)
        data_import, count = self.import_file("gbif.zip", self.gbif_download(
            [self.OBSERVATIONS[0], self.OBSERVATIONS[2], self.OBSERVATIONS[5], new]))
        self.assertEqual((count, data_import.error_numbers), (2, 1))  # Jeanne's 14 July again, and Paul
        self.assertEqual((CountingObject.objects.count(), CountingMeasure.objects.count()), (4, 4))

    def test_unknown_columns_are_refused(self):
        with self.assertRaisesMessage(ValueError, "Colonnes iNaturalist non reconnues"):
            self.import_file("other.zip", zip_bytes({"data.csv": "a,b\n1,2\n"}))

    def run_export(self):
        return self.import_file("iNaturalist-observations-1.csv", self.inaturalist_export())


class ParserDescriptionTests(SimpleTestCase):
    def test_every_parser_says_what_its_file_holds(self):
        for parser in (OutdoorVisionParser, StravaParser, CompteurParser, INaturalistParser):
            with self.subTest(parser.__name__):
                self.assertTrue(parser.CONTENT.startswith("Contient des "))


def cell(xmin, ymin, xmax, ymax):
    """WGS84 square as ``geom_4326`` plus its Lambert-93 ``geom``."""
    wgs84 = MultiPolygon(Polygon.from_bbox((xmin, ymin, xmax, ymax)), srid=4326)
    return {"geom_4326": wgs84, "geom": wgs84.transform(2154, clone=True)}


class AreasTestCase(TestCase):
    """The view needs ref_geo, which the test database does not have. Its
    tables are created inside the test transaction, before the counting
    objects, so the trigger of migration 0003 fills counting_object_areas.

    Sources s1 / s2, two M1 cells (12 and 13), one object per (cell, source, type):
        cell 12: 2023-01 s1 10 (4 segment, 6 presence), 2023-01 s2 5 (5, 0),
                 2023-02 s1 7 (0, 7)
        cell 13: 2023-01 s1 4 (0, 4), 2024-01 s2 3 (3, 0)
    """

    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS ref_geo")
        with connection.schema_editor() as editor:
            for model in (BibAreasType, LArea):
                editor.create_model(model)

        m1 = BibAreasType.objects.create(type_name="Mailles 1km", type_code="M1")
        LArea.objects.create(id_area=12, type=m1, area_code="A", **cell(6.0, 44.0, 6.5, 44.5))
        LArea.objects.create(id_area=13, type=m1, area_code="B", **cell(7.0, 44.0, 7.5, 44.5))

        cls.s1 = DataSource.objects.get(code="outdoorvision").pk
        cls.s2 = DataSource.objects.get(code="ecocompteur").pk
        cls.weights = f"{cls.s1}:2,{cls.s2}:3"
        types = {t.code: t for t in CountingObjectType.objects.all()}
        person = Unit.objects.get(code="person")
        centers = {12: (6.2, 44.2), 13: (7.2, 44.2)}

        def make(id_area, source, type_code, measures):
            x, y = centers[id_area]
            geom = (
                LineString((x, y), (x + 0.01, y + 0.01), srid=4326)
                if type_code == "segment"
                else Point(x, y, srid=4326)
            )
            obj = CountingObject.objects.create(
                type=types[type_code], source_id=source, geom=geom
            )
            for year, month, count in measures:
                start = datetime(year, month, 10, tzinfo=timezone.utc)
                CountingMeasure.objects.create(
                    counting_object=obj, start_datetime=start,
                    end_datetime=start + timedelta(days=1), count=count, unit=person,
                )
            return obj

        make(12, cls.s1, "counter", [(2023, 1, 6), (2023, 2, 7)])
        make(12, cls.s1, "segment", [(2023, 1, 4)])
        make(12, cls.s2, "segment", [(2023, 1, 5)])
        make(13, cls.s1, "counter", [(2023, 1, 4)])
        cls.moving = make(13, cls.s2, "segment", [(2024, 1, 3)])


class BasicFrequentationScoreTests(AreasTestCase):
    def test_sums_every_source_and_month(self):
        self.assertEqual(BasicFrequentationScore.compute(), {12: 22, 13: 7})

    def test_filters_on_period_and_source(self):
        def basic(date_from=None, date_to=None):
            return BasicFrequentationScore.compute(date_from=date_from, date_to=date_to)

        self.assertEqual(basic(date(2023, 1, 1), date(2023, 1, 31)), {12: 15, 13: 4})
        # Both bounds included: the January measures start on 2023-01-10 at 00:00.
        self.assertEqual(basic(date(2023, 1, 10), date(2023, 1, 10)), {12: 15, 13: 4})
        self.assertEqual(basic(date_to=date(2023, 1, 9)), {})
        self.assertEqual(basic(date(2023, 1, 11), date(2023, 12, 31)), {12: 7})
        self.assertEqual(basic(date_from=date(2024, 1, 1)), {13: 3})
        self.assertEqual(BasicFrequentationScore.compute(sources=[self.s2]), {12: 5, 13: 3})

    def test_filters_on_cells(self):
        self.assertEqual(BasicFrequentationScore.compute(geom_ids=[12]), {12: 22})
        inside_13 = Point(7.2, 44.2, srid=4326)
        self.assertEqual(BasicFrequentationScore.compute(geoms=inside_13), {13: 7})
        self.assertEqual(
            BasicFrequentationScore.compute(geoms=inside_13, geom_ids=[12]), {12: 22, 13: 7}
        )
        self.assertEqual(BasicFrequentationScore.compute(geom_ids=[]), {})


class CazalisFrequentationScoreTests(AreasTestCase):
    def test_applies_source_weights_per_area(self):
        score_grid = CazalisFrequentationScore.compute(
            date_from=date(2023, 1, 1), date_to=date(2023, 12, 31),
            source_weights={self.s1: 2, self.s2: 3},
        )
        # cell 12: (10 + 7) * 2 + 5 * 3; cell 13: 4 * 2
        self.assertEqual(score_grid, {12: 49, 13: 8})

    def test_rejects_missing_source_weight(self):
        with self.assertRaisesRegex(ValueError, f"Missing weight for source ID {self.s2}"):
            CazalisFrequentationScore.compute(source_weights={self.s1: 1})

    def test_requires_source_weights(self):
        with self.assertRaises(ValueError):
            CazalisFrequentationScore.compute()


class AreasApiTests(AreasTestCase):
    url = "/api/traffic/areas"

    def test_returns_geojson_with_counts_and_scores(self):
        response = self.client.get(self.url, {
            "date_from": "2023-01-01", "date_to": "2023-01-31",
            "scores": ["basic", "cazalis"], "source_weights": self.weights,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(data["count"], 2)
        features = {f["id"]: f for f in data["features"]}
        self.assertEqual(features[12]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(features[12]["properties"], {
            "counts": 15, "count_segment": 9, "count_presence": 6,
            "score": {"basic": 15, "cazalis": 35.0},
        })
        self.assertEqual(features[13]["properties"], {
            "counts": 4, "count_segment": 0, "count_presence": 4,
            "score": {"basic": 4, "cazalis": 8.0},
        })

    def test_filters_on_source_and_bbox(self):
        response = self.client.get(self.url, {"source": [self.s2], "bbox": "6.9,43.9,7.6,44.6"})
        features = response.json()["features"]
        self.assertEqual([f["id"] for f in features], [13])
        self.assertEqual(features[0]["properties"]["counts"], 3)
        self.assertEqual(features[0]["properties"]["score"], {})

    def test_cazalis_needs_a_weight_for_every_source(self):
        response = self.client.get(self.url, {"scores": "cazalis"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_weights", response.json())
        response = self.client.get(self.url, {"scores": "cazalis", "source_weights": f"{self.s1}:2"})
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_finite_source_weights(self):
        for weight in ("nan", "inf", "-inf"):
            weights = f"{self.s1}:{weight},{self.s2}:1"
            response = self.client.get(self.url, {"scores": "cazalis", "source_weights": weights})
            self.assertEqual(response.status_code, 400, weights)
            self.assertIn("source_weights", response.json())

    def test_spatial_filters_of_ref_geo(self):
        def ids(**params):
            return [f["id"] for f in self.client.get(self.url, params).json()["features"]]

        self.assertEqual(ids(in_bbox="6.9,43.9,7.6,44.6"), [13])
        self.assertEqual(ids(point="6.2,44.2"), [12])
        self.assertEqual(ids(intersects="POLYGON((6.1 44.1,7.2 44.1,7.2 44.2,6.1 44.2,6.1 44.1))"), [12, 13])
        self.assertEqual(ids(area_code="B"), [13])

    def test_rejects_invalid_parameters(self):
        response = self.client.get(self.url, {"date_from": "2023-13-01", "scores": "foo"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"date_from", "scores"})
        response = self.client.get(self.url, {"date_from": "2023-02-01", "date_to": "2023-01-31"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_to", response.json())
        self.assertEqual(self.client.get(self.url, {"bbox": "x"}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"in_bbox": "x"}).status_code, 400)

    def test_only_cells_with_matching_measures(self):
        response = self.client.get(self.url, {"date_from": "2024-01-01"})
        self.assertEqual([f["id"] for f in response.json()["features"]], [13])

    def test_paginates_and_scores_the_page(self):
        response = self.client.get(self.url, {"limit": 1, "offset": 1, "scores": "basic"})
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(data["count"], 2)
        self.assertIsNone(data["next"])
        self.assertIsNotNone(data["previous"])
        self.assertEqual([f["id"] for f in data["features"]], [13])
        self.assertEqual(data["features"][0]["properties"]["score"], {"basic": 7})

    def test_retrieve_one_cell(self):
        response = self.client.get(f"{self.url}/12", {"source": self.s1, "scores": "basic"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "Feature")
        self.assertEqual(data["id"], 12)
        self.assertEqual(data["properties"], {
            "counts": 17, "count_segment": 4, "count_presence": 13, "score": {"basic": 17},
        })

    def test_retrieve_cell_without_matching_measures(self):
        self.assertEqual(self.client.get(f"{self.url}/12", {"date_from": "2024-01-01"}).status_code, 404)


class CountingObjectAreasTests(AreasTestCase):
    def areas(self, obj):
        return set(obj.areas.values_list("area_id", flat=True))

    def test_trigger_fills_and_follows_the_geometry(self):
        self.assertEqual(self.areas(self.moving), {13})
        self.moving.geom = LineString((6.4, 44.2), (7.2, 44.2), srid=4326)  # crosses 12 and 13
        self.moving.save()
        self.assertEqual(self.areas(self.moving), {12, 13})
        self.moving.geom = Point(8.0, 44.2, srid=4326)  # outside the grid
        self.moving.save()
        self.assertEqual(self.areas(self.moving), set())

    def test_segment_counts_in_every_cell_it_crosses(self):
        self.moving.geom = LineString((6.4, 44.2), (7.2, 44.2), srid=4326)
        self.moving.save()
        self.assertEqual(
            BasicFrequentationScore.compute(date_from=date(2024, 1, 1), sources=[self.s2]), {12: 3, 13: 3}
        )

    def test_sync_command_rebuilds_the_table(self):
        CountingObjectArea.objects.all().delete()
        call_command("sync_counting_object_areas", stdout=StringIO())
        self.assertEqual(CountingObjectArea.objects.count(), 5)

    def test_deleting_an_object_deletes_its_cells(self):
        pk = self.moving.pk  # delete() sets self.moving.pk to None
        self.moving.delete()
        self.assertFalse(CountingObjectArea.objects.filter(counting_object_id=pk).exists())


class SyncCommandWithoutRefGeoTests(TestCase):
    """The test database has no ref_geo schema."""

    def test_fails_without_ref_geo(self):
        with self.assertRaisesRegex(CommandError, "ref_geo schema missing"):
            call_command("sync_counting_object_areas")
