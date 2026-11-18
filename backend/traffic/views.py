import json
import math

from commons.models import DataSource
from django.conf import settings
from django.contrib.gis.geos import Polygon
from ref_geo.models import LArea
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from workshop2026.processing.score import (
    BasicFrequentationScore,
    CazalisFrequentationScore,
)


class ScoreSourcesView(APIView):
    def get(self, request):
        sources = DataSource.objects.order_by("label").values("id", "code", "label")
        return Response(list(sources))


class ScoreMapView(APIView):
    def get(self, request):
        indicator = request.query_params.get("indicator", "frequentation")
        if indicator not in {"frequentation", "cazalis"}:
            return Response(
                {"detail": "indicator must be 'frequentation' or 'cazalis'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_bbox = request.query_params.get("bbox", "5.5,44.4,7.0,45.5")
        try:
            west, south, east, north = (float(value) for value in raw_bbox.split(","))
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValueError
            if east - west > 2.5 or north - south > 2.5:
                return Response(
                    {"detail": "Zoom in to an area no larger than 2.5 degrees."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"detail": "bbox must be west,south,east,north within a 2.5-degree extent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        viewport = Polygon.from_bbox((west, south, east, north))
        viewport.srid = 4326

        areas = list(
            LArea.objects.filter(
                type__type_code=settings.DEFAULT_GRID_AREA_TYPE,
                enable=True,
                geom_4326__isnull=False,
                geom_4326__intersects=viewport,
            ).order_by("id_area")
        )
        area_ids = [area.id_area for area in areas]

        if indicator == "frequentation":
            scores = BasicFrequentationScore.compute(geom_ids=area_ids)
        else:
            try:
                raw_weights = json.loads(request.query_params.get("weights", "{}"))
                if not isinstance(raw_weights, dict):
                    raise ValueError
                weights = {
                    int(source_id): float(weight)
                    for source_id, weight in raw_weights.items()
                }
                if any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
                    raise ValueError
            except (TypeError, ValueError, json.JSONDecodeError):
                return Response(
                    {"detail": "weights must be a JSON object of non-negative numbers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                scores = CazalisFrequentationScore.compute(
                    geom_ids=area_ids,
                    source_weights=weights,
                )
            except ValueError as error:
                return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        features = [
            {
                "type": "Feature",
                "id": area.id_area,
                "geometry": json.loads(area.geom_4326.geojson),
                "properties": {
                    "id_area": area.id_area,
                    "area_name": area.area_name or area.area_code or str(area.id_area),
                    "area_code": area.area_code,
                    "score": scores.get(area.id_area, 0),
                },
            }
            for area in areas
        ]
        return Response({"type": "FeatureCollection", "features": features})
