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
from .serializers import (
    CountingMeasureSerializer,
    CountingObjectSerializer,
    CountingObjectTypeSerializer,
    GeometrySearchSerializer,
    AreasQuerySerializer,
    UnitSerializer,
)
from ref_geo.models import LArea
from workshop2026.processing.score import SCORES, counts_queryset

class UnitViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Unit.objects.order_by("id")
    serializer_class = UnitSerializer

class CountingObjectTypeViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CountingObjectType.objects.order_by("id")
    serializer_class = CountingObjectTypeSerializer


class CountingObjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CountingObject.objects.with_data_range().order_by("date_create")
    serializer_class = CountingObjectSerializer
    pagination_class = GeoJsonPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type"]

    @extend_schema(
        request=GeometrySearchSerializer,
        responses=CountingObjectSerializer(many=True),
    )
    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        input_serializer = GeometrySearchSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        geom = input_serializer.validated_data["geometry"]
        predicate = input_serializer.validated_data["predicate"]

        # Applique aussi les filtres en query string (ex: ?type=2)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(**{f"geom__{predicate}": geom})

        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)


class CountingMeasureViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CountingMeasure.objects.order_by("counting_object_id")
    serializer_class = CountingMeasureSerializer
    pagination_class = PageNumberPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["counting_object"]


class AreasView(APIView):
    """Counts and scores per 1 km grid cell, as a GeoJSON FeatureCollection.

    One feature per cell that has measures matching the filters, with the
    properties ``counts``, ``count_segment``, ``count_presence`` and ``score``
    (``{score name: value}`` for the requested ``scores``). Geometry in WGS84.
    """

    @extend_schema(parameters=[AreasQuerySerializer], responses={200: OpenApiTypes.OBJECT})
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
                "geometry": json.loads(area.geom_4326.geojson) if area.geom_4326 else None,
                "properties": {
                    **totals[area.id_area],
                    "score": {
                        name: values.get(area.id_area, 0) for name, values in scores.items()
                    },
                },
            }
            for area in areas.order_by("id_area")
        ]
        return Response({"type": "FeatureCollection", "features": features})
