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


def square(xmin, ymin, xmax, ymax, srid):
    poly = Polygon.from_bbox((xmin, ymin, xmax, ymax))
    poly.srid = srid
    return MultiPolygon(poly, srid=srid)


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
            geom_4326=square(6.8, 45.9, 6.9, 46.0, 4326),
        )
        cls.paris = LArea.objects.create(
            type=cls.com,
            area_name="Paris",
            area_code="75056",
            geom_4326=square(2.2, 48.8, 2.5, 48.9, 4326),
        )
        cls.cell = LArea.objects.create(
            type=cls.m1,
            area_name="E090N6839",
            area_code="1kmL93E090N6839",
            geom_4326=square(6.85, 45.92, 6.86, 45.93, 4326),
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
