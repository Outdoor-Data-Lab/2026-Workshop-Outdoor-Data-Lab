from commons.api.geo import GeoViewSet, ReadOnlyViewSet
import json

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_gis.pagination import GeoJsonPagination

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)
from .filters import CountingMeasureFilter, CountingObjectFilter
from .serializers import (
    CountingMeasureSerializer,
    CountingObjectGeoSerializer,
    CountingObjectSerializer,
    CountingObjectTypeSerializer,
    GeometrySearchSerializer,
    AreasQuerySerializer,
    UnitSerializer,
)
from ref_geo.models import LArea
from workshop2026.processing.score import SCORES, counts_queryset


class UnitViewSet(ReadOnlyViewSet):
    queryset = Unit.objects.order_by("id")
    serializer_class = UnitSerializer
    filterset_fields = ["code"]
    ordering_fields = ("id", "code", "label")


class CountingObjectTypeViewSet(ReadOnlyViewSet):
    queryset = CountingObjectType.objects.order_by("id")
    serializer_class = CountingObjectTypeSerializer
    filterset_fields = ["code"]
    ordering_fields = ("id", "code", "label")


class CountingObjectViewSet(GeoViewSet):
    queryset = (
        CountingObject.objects.with_data_range()
        .select_related("type", "source", "origin")
        .order_by("id")
    )
    serializer_class = CountingObjectSerializer
    geo_serializer_class = CountingObjectGeoSerializer
    filterset_class = CountingObjectFilter
    ordering_fields = ("id", "external_id", "installation_date", "date_update")

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if self.is_geojson() else queryset.defer("geom")


class CountingMeasureViewSet(ReadOnlyViewSet):
    # Unique order, so that pages do not skip or repeat measures.
    queryset = CountingMeasure.objects.select_related("unit", "practice").order_by(
        "counting_object_id", "start_datetime", "id"
    )
    serializer_class = CountingMeasureSerializer
    filterset_class = CountingMeasureFilter
    ordering_fields = ("id", "start_datetime", "end_datetime", "count")
    pagination_class = PageNumberPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["counting_object"]


class AreasView(APIView):
    """Counts and scores per 1 km grid cell, as a GeoJSON FeatureCollection.

    One feature per cell that has measures matching the filters, with the
    properties ``counts``, ``count_segment``, ``count_presence`` and ``score``
    (``{score name: value}`` for the requested ``scores``). Geometry in WGS84.
    """

    @extend_schema(
        parameters=[AreasQuerySerializer], responses={200: OpenApiTypes.OBJECT}
    )
    def get(self, request):
        params = AreasQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        params = params.validated_data

        queryset = counts_queryset(
            geoms=params.get("bbox"),
            sources=params.get("source"),
            year=params.get("year"),
            month=params.get("month"),
        )
        totals = queryset.values("id_area").annotate(
            counts=Sum("counts"),
            count_segment=Sum("count_segment"),
            count_presence=Sum("count_presence"),
        )
        try:
            scores = {
                name: SCORES[name].compute_from(
                    queryset, source_weights=params.get("source_weights")
                )
                for name in sorted(params.get("scores", ()))
            }
        except ValueError as error:
            raise serializers.ValidationError({"source_weights": [str(error)]})

        totals = {row.pop("id_area"): row for row in totals}
        areas = LArea.objects.filter(id_area__in=totals).only("id_area", "geom_4326")
        features = [
            {
                "type": "Feature",
                "id": area.id_area,
                "geometry": (
                    json.loads(area.geom_4326.geojson) if area.geom_4326 else None
                ),
                "properties": {
                    **totals[area.id_area],
                    "score": {
                        name: values.get(area.id_area, 0)
                        for name, values in scores.items()
                    },
                },
            }
            for area in areas.order_by("id_area")
        ]
        return Response({"type": "FeatureCollection", "features": features})
