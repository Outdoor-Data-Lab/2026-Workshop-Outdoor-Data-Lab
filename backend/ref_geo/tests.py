"""Tests for the read-only ref_geo API.

The ref_geo tables come from the RefGeo dump and are unmanaged, so the test
database does not have them: setUpTestData creates the schema and tables inside
the test transaction (rolled back afterwards).
"""

import json
from urllib.parse import quote

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import (
    BibAreasType,
    BibLinearsType,
    BibPointsType,
    CorLinearGroup,
    LArea,
    LiGrid,
    LiMunicipality,
    LLinear,
    LPoint,
    TLinearGroup,
)

MODELS = [
    BibAreasType,
    BibLinearsType,
    BibPointsType,
    LArea,
    LLinear,
    LPoint,
    LiMunicipality,
    LiGrid,
    TLinearGroup,
    CorLinearGroup,
]


def square(xmin, ymin, xmax, ymax, srid=4326):
    poly = Polygon.from_bbox((xmin, ymin, xmax, ymax))
    poly.srid = srid
    return MultiPolygon(poly, srid=srid)


def both_geoms(xmin, ymin, xmax, ymax):
    """WGS84 square as ``geom_4326`` plus its Lambert-93 ``geom``.

    The spatial filters use ``geom`` (indexed), the GeoJSON output ``geom_4326``.
    """
    wgs84 = square(xmin, ymin, xmax, ymax)
    return {"geom_4326": wgs84, "geom": wgs84.transform(2154, clone=True)}


class RefGeoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS ref_geo")
        with connection.schema_editor() as editor:
            for model in MODELS:
                editor.create_model(model)

        cls.com = BibAreasType.objects.create(type_name="Communes", type_code="COM")
        cls.m1 = BibAreasType.objects.create(type_name="Mailles 1km", type_code="M1")
        # Two areas in WGS84 (the API reads geom_4326), far from each other.
        cls.chamonix = LArea.objects.create(
            type=cls.com,
            area_name="Chamonix-Mont-Blanc",
            area_code="74056",
            **both_geoms(6.8, 45.9, 6.9, 46.0),
        )
        cls.paris = LArea.objects.create(
            type=cls.com,
            area_name="Paris",
            area_code="75056",
            **both_geoms(2.2, 48.8, 2.5, 48.9),
        )
        cls.cell = LArea.objects.create(
            type=cls.m1,
            area_name="E090N6839",
            area_code="1kmL93E090N6839",
            **both_geoms(6.85, 45.92, 6.86, 45.93),
        )
        LiMunicipality.objects.create(
            id_municipality="COMMUNE_1",
            area=cls.chamonix,
            insee_com="74056",
            nom_com="Chamonix-Mont-Blanc",
            insee_dep="74",
        )
        LiGrid.objects.create(id_grid="1kmL93E090N6839", area=cls.cell, cxmin=0)

        lin_type = BibLinearsType.objects.create(type_name="Sentiers", type_code="SENT")
        cls.linear = LLinear.objects.create(
            type=lin_type,
            linear_name="GR5",
            linear_code="GR5",
            # Lambert-93 coordinates around Chamonix
            geom=Point(1000000, 6500000, srid=2154).buffer(10),
        )
        pt_type = BibPointsType.objects.create(type_name="Refuges", type_code="REF")
        cls.point = LPoint.objects.create(
            type=pt_type,
            point_name="Refuge",
            point_code="R1",
            geom=Point(1000000, 6500000, srid=2154),
        )

    def get(self, name, query="", **kwargs):
        url = reverse(f"ref_geo:{name}", kwargs=kwargs or None)
        response = self.client.get(f"{url}?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def codes(self, data):
        return {a["area_code"] for a in data["results"]}


class ReferenceTablesTests(RefGeoTestCase):
    def test_area_types_list_and_filter(self):
        data = self.get("area-type-list", "type_code=COM")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["type_name"], "Communes")

    def test_municipalities_filter_by_name(self):
        data = self.get("municipality-list", "name=chamo")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["insee_com"], "74056")

    def test_grids_filter_by_area(self):
        data = self.get("grid-list", f"area={self.cell.pk}")
        self.assertEqual(data["count"], 1)

    def test_linears_and_points_listed(self):
        self.assertEqual(self.get("linear-list")["results"][0]["type_code"], "SENT")
        self.assertEqual(self.get("point-list")["results"][0]["point_code"], "R1")

    def test_api_is_read_only(self):
        response = self.client.post(reverse("ref_geo:area-list"), {})
        self.assertEqual(response.status_code, 405)

    def test_dynamic_fields_filtering(self):
        """Test DynamicFieldsMixin filters fields correctly for all serializers in ref_geo.serializers."""
        # Test BibAreasTypeSerializer via API endpoint
        response = self.client.get(reverse("ref_geo:area-type-list"), {"fields": "id_type,type_code"})
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertIn("id_type", result)
        self.assertIn("type_code", result)
        self.assertNotIn("type_name", result)
        self.assertNotIn("ref_name", result)
        self.assertEqual(set(result.keys()), {"id_type", "type_code"})

class AreaFilterTests(RefGeoTestCase):
    def test_json_has_no_geometry(self):
        data = self.get("area-list")
        self.assertEqual(data["count"], 3)
        self.assertNotIn("geometry", data["results"][0])
        self.assertNotIn("geom_4326", data["results"][0])

    def test_filter_type_code(self):
        data = self.get("area-list", "type_code=M1")
        self.assertEqual(self.codes(data), {"1kmL93E090N6839"})

    def test_filter_name_icontains(self):
        data = self.get("area-list", "name=paris")
        self.assertEqual(self.codes(data), {"75056"})

    def test_pagination_limit(self):
        data = self.get("area-list", "limit=1")
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 1)
        self.assertIsNotNone(data["next"])

    def test_bbox(self):
        data = self.get("area-list", "type_code=COM&bbox=6.8,45.9,6.9,46.0")
        self.assertEqual(self.codes(data), {"74056"})

    def test_bbox_invalid(self):
        response = self.client.get(reverse("ref_geo:area-list"), {"bbox": "x"})
        self.assertEqual(response.status_code, 400)

    def test_point(self):
        data = self.get("area-list", "type_code=COM&point=6.87,45.92")
        self.assertEqual(self.codes(data), {"74056"})

    def test_point_invalid(self):
        response = self.client.get(reverse("ref_geo:area-list"), {"point": "1"})
        self.assertEqual(response.status_code, 400)

    def test_intersects_geojson_and_wkt(self):
        geojson = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[6.8, 45.9], [6.9, 45.9], [6.9, 46.0], [6.8, 46.0], [6.8, 45.9]]
                ],
            }
        )
        wkt = "POLYGON((6.8 45.9,6.9 45.9,6.9 46,6.8 46,6.8 45.9))"
        for geom in (geojson, wkt):
            data = self.get("area-list", f"type_code=COM&intersects={quote(geom)}")
            self.assertEqual(self.codes(data), {"74056"})

    def test_within(self):
        wkt = "POLYGON((6.0 45.0,7.0 45.0,7.0 47.0,6.0 47.0,6.0 45.0))"
        data = self.get("area-list", f"within={quote(wkt)}")
        self.assertEqual(self.codes(data), {"74056", "1kmL93E090N6839"})

    def test_contains(self):
        wkt = "POINT(6.855 45.925)"
        data = self.get("area-list", f"contains={quote(wkt)}")
        self.assertEqual(self.codes(data), {"74056", "1kmL93E090N6839"})

    def test_invalid_geometry(self):
        response = self.client.get(reverse("ref_geo:area-list"), {"intersects": "junk"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("intersects", response.json())

    def test_linear_spatial_filter_reprojects_input(self):
        # linears are stored in Lambert-93; the WGS84 input is reprojected
        lon_lat = Point(1000000, 6500000, srid=2154).transform(4326, clone=True)
        data = self.get("linear-list", f"point={lon_lat.x},{lon_lat.y}")
        self.assertEqual(data["count"], 1)


class GeoJSONTests(RefGeoTestCase):
    def get_geojson(self, name, query="", **kwargs):
        return self.get(name, f"format=geojson&{query}", **kwargs)

    def test_feature_collection(self):
        data = self.get_geojson("area-list", "type_code=COM")
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(data["count"], 2)
        feature = data["features"][0]
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["type"], "MultiPolygon")
        self.assertIn("area_code", feature["properties"])
        self.assertNotIn("geom_4326", feature["properties"])

    def test_content_type(self):
        response = self.client.get(reverse("ref_geo:area-list"), {"format": "geojson"})
        self.assertEqual(response["Content-Type"], "application/geo+json")

    def test_pagination_keeps_format(self):
        data = self.get_geojson("area-list", "limit=1")
        self.assertEqual(len(data["features"]), 1)
        self.assertIn("format=geojson", data["next"])

    def test_single_feature(self):
        data = self.get_geojson("area-detail", pk=self.chamonix.pk)
        self.assertEqual(data["type"], "Feature")
        self.assertEqual(data["id"], self.chamonix.pk)
        self.assertEqual(data["properties"]["area_name"], "Chamonix-Mont-Blanc")

    def test_geojson_filters_combine(self):
        data = self.get_geojson("area-list", "type_code=COM&point=6.87,45.92")
        self.assertEqual(data["count"], 1)

    def test_linear_geometry_is_wgs84(self):
        data = self.get_geojson("linear-list")
        x, y = data["features"][0]["geometry"]["coordinates"][0][0]
        # Lambert-93 values would be ~1e6; WGS84 are small lon/lat degrees
        self.assertLess(abs(x), 180)
        self.assertLess(abs(y), 90)

    def test_point_geometry_is_wgs84(self):
        data = self.get_geojson("point-list")
        x, y = data["features"][0]["geometry"]["coordinates"]
        self.assertLess(abs(x), 180)
        self.assertLess(abs(y), 90)


class RobustnessTests(RefGeoTestCase):
    def status(self, params, **extra):
        return self.client.get(reverse("ref_geo:area-list"), params, **extra).status_code

    def test_nan_and_inf_are_400(self):
        self.assertEqual(self.status({"bbox": "nan,nan,nan,nan"}), 400)
        self.assertEqual(self.status({"bbox": "0,0,inf,1"}), 400)
        self.assertEqual(self.status({"point": "nan,1"}), 400)

    def test_unknown_srid_is_400(self):
        self.assertEqual(self.status({"intersects": "SRID=99999;POINT(1 1)"}), 400)

    def test_known_ewkt_srid_is_reprojected(self):
        point = Point(6.87, 45.92, srid=4326).transform(2154, clone=True)
        ewkt = f"SRID=2154;POINT({point.x} {point.y})"
        data = self.get("area-list", f"type_code=COM&intersects={quote(ewkt)}")
        self.assertEqual(self.codes(data), {"74056"})

    def test_geojson_with_accept_json_header(self):
        response = self.client.get(
            reverse("ref_geo:area-list"),
            {"format": "geojson"},
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/geo+json")

    def test_ordering_is_whitelisted(self):
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.status({"ordering": "geom_4326"}), 200)
        order_by = ctx.captured_queries[-1]["sql"].split("ORDER BY")[-1]
        self.assertNotIn("geom_4326", order_by)  # unknown field: dropped
        data = self.get("area-list", "type_code=COM&ordering=-area_name")
        self.assertEqual(
            [a["area_name"] for a in data["results"]],
            ["Paris", "Chamonix-Mont-Blanc"],
        )

    def test_views_work_without_request_for_schema_generation(self):
        # Schema generators instantiate views with no request (or an unrendered one)
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from .views import LAreaViewSet, LLinearViewSet, LPointViewSet

        for viewset in (LAreaViewSet, LLinearViewSet, LPointViewSet):
            view = viewset()
            self.assertFalse(view.is_geojson())  # no request at all
            view.request = Request(APIRequestFactory().get("/"))  # no accepted_renderer
            self.assertFalse(view.is_geojson())
            self.assertIsNotNone(view.get_serializer_class())
            view.get_queryset()

    def test_linear_queries_do_not_load_native_geometry(self):
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.get("linear-list", "format=geojson")
        select = ctx.captured_queries[-1]["sql"].split(" FROM ")[0]
        self.assertIn("ST_Transform", select)
        # the only use of the native column is inside ST_Transform
        self.assertEqual(select.count('"l_linears"."geom"'), 1)
