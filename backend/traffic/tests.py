from datetime import datetime, timedelta, timezone
from calendar import monthrange
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import Client, SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory

from commons.models import DataSource, Practice
from ref_geo.models import BibAreasType, LArea
from workshop2026.models import MaterializedViewCount
from workshop2026.processing.score import (
    BasicFrequentationScore,
    CazalisFrequentationScore,
    cazalis_weights_from_correlations,
)
from traffic.views import ScoreMapView, ScoreSourcesView

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


def cell(xmin, ymin, xmax, ymax):
    """WGS84 square as ``geom_4326`` plus its Lambert-93 ``geom``."""
    wgs84 = MultiPolygon(Polygon.from_bbox((xmin, ymin, xmax, ymax)), srid=4326)
    return {"geom_4326": wgs84, "geom": wgs84.transform(2154, clone=True)}


class AreasTestCase(TestCase):
    """The view needs ref_geo, which the test database does not have (migration
    0003 skips it). The ref_geo tables and a plain table standing in for the
    view are created inside the test transaction.

    Source 1 / source 2, two M1 cells (12 and 13):
        cell 12: 2023-01 src1 10 (4 segment, 6 presence), 2023-01 src2 5 (5, 0),
                 2023-02 src1 7 (0, 7)
        cell 13: 2023-01 src1 4 (0, 4), 2024-01 src2 3 (3, 0)
    """

    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS ref_geo")
        with connection.schema_editor() as editor:
            for model in (BibAreasType, LArea, MaterializedViewCount):
                editor.create_model(model)

        m1 = BibAreasType.objects.create(type_name="Mailles 1km", type_code="M1")
        LArea.objects.create(id_area=12, type=m1, area_code="A", **cell(6.0, 44.0, 6.5, 44.5))
        LArea.objects.create(id_area=13, type=m1, area_code="B", **cell(7.0, 44.0, 7.5, 44.5))
        for id_area, id_source, year, month, counts, segment, presence in [
            (12, 1, 2023, 1, 10, 4, 6),
            (12, 2, 2023, 1, 5, 5, 0),
            (12, 1, 2023, 2, 7, 0, 7),
            (13, 1, 2023, 1, 4, 0, 4),
            (13, 2, 2024, 1, 3, 3, 0),
        ]:
            MaterializedViewCount.objects.create(
                id_area=id_area, id_source=id_source, year=year, month=month,
                counts=counts, count_segment=segment, count_presence=presence,
            )


class BasicFrequentationScoreTests(AreasTestCase):
    def test_sums_every_source_and_month(self):
        self.assertEqual(BasicFrequentationScore.compute(), {12: 22, 13: 7})

    def test_filters_on_year_month_and_source(self):
        self.assertEqual(BasicFrequentationScore.compute(year=2023, month=1), {12: 15, 13: 4})
        self.assertEqual(BasicFrequentationScore.compute(sources=[2]), {12: 5, 13: 3})

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
        score_grid = CazalisFrequentationScore.compute(year=2023, source_weights={1: 2, 2: 3})
        # cell 12: (10 + 7) * 2 + 5 * 3; cell 13: 4 * 2
        self.assertEqual(score_grid, {12: 49, 13: 8})

    def test_rejects_missing_source_weight(self):
        with self.assertRaisesRegex(ValueError, "Missing weight for source ID 2"):
            CazalisFrequentationScore.compute(source_weights={1: 1})

    def test_calculates_source_weights_when_not_provided(self):
        self.assertEqual(CazalisFrequentationScore.compute(), {12: 0, 13: 0})


class CazalisWeightFormulaTests(SimpleTestCase):
    def test_uses_bta_threshold_inverse_correlation_and_percentage_rounding(self):
        weights = cazalis_weights_from_correlations(
            {1: 0.5, 2: 0.75, 3: 0.25, 4: -0.2},
            [1, 2, 3, 4],
        )

        self.assertEqual(weights, {1: 33, 2: 67, 3: 0, 4: 0})
        self.assertEqual(sum(weights.values()), 100)


class CazalisWeightCalculationTests(AreasTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        eco_source = DataSource.objects.get(code="ecocompteur")
        strava_source = DataSource.objects.get(code="strava")
        outdoor_source = DataSource.objects.get(code="outdoorvision")
        source_daily_counts = [
            (12, 6, 10, 1, 1),
            (12, 7, 20, 3, 2),
            (13, 6, 30, 2, 4),
            (13, 7, 40, 5, 3),
        ]
        for area_id, month, eco_daily, strava_daily, outdoor_daily in source_daily_counts:
            days = monthrange(2021, month)[1]
            for source, daily_count in (
                (eco_source, eco_daily),
                (strava_source, strava_daily),
                (outdoor_source, outdoor_daily),
            ):
                MaterializedViewCount.objects.create(
                    id_area=area_id,
                    id_source=source.id,
                    year=2021,
                    month=month,
                    counts=daily_count * days,
                    count_segment=0,
                    count_presence=daily_count * days,
                )

    def test_calculates_weights_from_summer_ecocompteur_correlations(self):
        weights = CazalisFrequentationScore.calculate_source_weights()
        strava = DataSource.objects.get(code="strava")
        outdoor = DataSource.objects.get(code="outdoorvision")
        inaturalist = DataSource.objects.get(code="inaturalist")
        ecocompteur = DataSource.objects.get(code="ecocompteur")

        self.assertEqual(sum(weights.values()), 100)
        self.assertGreater(weights[strava.id], weights[outdoor.id])
        self.assertEqual(weights[inaturalist.id], 0)
        self.assertEqual(weights[ecocompteur.id], 0)


class AreasApiTests(AreasTestCase):
    url = "/api/traffic/areas"

    def test_returns_geojson_with_counts_and_scores(self):
        response = self.client.get(self.url, {
            "year": 2023, "month": 1,
            "scores": ["basic", "cazalis"], "source_weights": "1:2,2:3",
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
        response = self.client.get(self.url, {"source": [2], "bbox": "6.9,43.9,7.6,44.6"})
        features = response.json()["features"]
        self.assertEqual([f["id"] for f in features], [13])
        self.assertEqual(features[0]["properties"]["counts"], 3)
        self.assertEqual(features[0]["properties"]["score"], {})

    def test_cazalis_calculates_weights_when_omitted(self):
        response = self.client.get(self.url, {"scores": "cazalis"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("source_weights", response.json())
        self.assertEqual(sum(response.json()["source_weights"].values()), 0)

        response = self.client.get(self.url, {"scores": "cazalis", "source_weights": "1:2"})
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_parameters(self):
        response = self.client.get(self.url, {"month": 13, "scores": "foo", "bbox": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"month", "scores", "bbox"})

    def test_only_cells_with_matching_measures(self):
        response = self.client.get(self.url, {"year": 2024})
        self.assertEqual([f["id"] for f in response.json()["features"]], [13])

    def test_paginates_and_scores_the_page(self):
        response = self.client.get(self.url, {"page_size": 1, "page": 2, "scores": "basic"})
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([f["id"] for f in data["features"]], [13])
        self.assertEqual(data["features"][0]["properties"]["score"], {"basic": 7})

    def test_retrieve_one_cell(self):
        response = self.client.get(f"{self.url}/12", {"source": 1, "scores": "basic"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "Feature")
        self.assertEqual(data["id"], 12)
        self.assertEqual(data["properties"], {
            "counts": 17, "count_segment": 4, "count_presence": 13, "score": {"basic": 17},
        })

    def test_retrieve_cell_without_matching_measures(self):
        self.assertEqual(self.client.get(f"{self.url}/12", {"year": 2024}).status_code, 404)


class ScoreApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.area = SimpleNamespace(
            id_area=12,
            area_name="Maille 12",
            area_code="M12",
            geom_4326=SimpleNamespace(
                geojson='{"type":"MultiPolygon","coordinates":[]}'
            ),
        )

    @patch("traffic.views.LArea.objects.filter")
    @patch("traffic.views.BasicFrequentationScore.compute")
    def test_score_map_returns_scored_geojson(self, compute_score, filter_areas):
        filter_areas.return_value.order_by.return_value = [self.area]
        compute_score.return_value = {12: 25}

        response = ScoreMapView.as_view()(self.factory.get("/traffic/score-map/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "FeatureCollection")
        self.assertEqual(response.data["features"][0]["id"], 12)
        self.assertEqual(response.data["features"][0]["properties"]["score"], 25)
        compute_score.assert_called_once_with(geom_ids=[12])

    @patch("traffic.views.LArea.objects.filter")
    @patch("traffic.views.CazalisFrequentationScore.compute")
    def test_cazalis_weights_are_forwarded(self, compute_score, filter_areas):
        filter_areas.return_value.order_by.return_value = [self.area]
        compute_score.return_value = {12: 50}
        request = self.factory.get(
            "/traffic/score-map/",
            {"indicator": "cazalis", "weights": '{"3": 2.5}'},
        )

        response = ScoreMapView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        compute_score.assert_called_once_with(
            geom_ids=[12],
            source_weights={3: 2.5},
        )

    @patch("traffic.views.DataSource.objects.order_by")
    def test_sources_endpoint_returns_source_metadata(self, order_sources):
        order_sources.return_value.values.return_value = [
            {"id": 3, "code": "outdoorvision", "label": "OutdoorVision"}
        ]

        response = ScoreSourcesView.as_view()(self.factory.get("/traffic/sources/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], 3)
