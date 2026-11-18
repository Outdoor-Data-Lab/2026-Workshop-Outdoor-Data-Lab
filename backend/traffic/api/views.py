from functools import cached_property

from django.db.models import OuterRef, Subquery, Sum
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework_gis.filters import InBBoxFilter

from commons.api.geo import GeoJsonLimitOffsetPagination, GeoViewSet, ReadOnlyViewSet
from ref_geo.filters import LAreaFilter
from ref_geo.models import LArea
from workshop2026.processing.score import SCORES, counts_queryset

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)
from .filters import CountingMeasureFilter, CountingObjectFilter
from .serializers import (
    AreaCountsSerializer,
    AreasQuerySerializer,
    CountingMeasureSerializer,
    CountingObjectGeoSerializer,
    CountingObjectSerializer,
    CountingObjectTypeSerializer,
    UnitSerializer,
)


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


@extend_schema_view(
    list=extend_schema(parameters=[AreasQuerySerializer]),
    retrieve=extend_schema(parameters=[AreasQuerySerializer]),
)
class AreasViewSet(viewsets.ReadOnlyModelViewSet):
    """Counts and scores per 1 km grid cell (ref_geo "M1"), as GeoJSON.

    Only the cells with measures matching ``source``, ``year`` and ``month``.
    Properties: ``counts``, ``count_segment``, ``count_presence`` and ``score``
    (``{score name: value}`` for the requested ``scores``). Geometry in WGS84.
    Scores are computed for the cells of the page only.

    Spatial filters on the cells, as in ref_geo: ``bbox``, ``point``,
    ``intersects``, ``within``, ``contains`` (LAreaFilter, on the indexed
    Lambert-93 geometry) and ``in_bbox`` (rest_framework_gis). Pagination:
    ``limit`` / ``offset``.
    """

    serializer_class = AreaCountsSerializer
    lookup_field = "id_area"
    pagination_class = GeoJsonLimitOffsetPagination
    filter_backends = [DjangoFilterBackend, InBBoxFilter]
    filterset_class = LAreaFilter
    # InBBoxFilter builds its box without an SRID: it must target the WGS84 column.
    bbox_filter_field = "geom_4326"
    bbox_filter_include_overlapping = True

    @cached_property
    def params(self):
        serializer = AreasQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @cached_property
    def counts(self):
        """Rows of the materialized view matching source, year and month."""
        return counts_queryset(
            sources=self.params.get("source"),
            year=self.params.get("year"),
            month=self.params.get("month"),
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI schema generation
            return LArea.objects.none()
        queryset = LArea.objects.filter(
            type__type_code="M1", id_area__in=self.counts.values("id_area")
        )

        def total(column):
            return Subquery(
                self.counts.filter(id_area=OuterRef("id_area"))
                .values("id_area")
                .annotate(total=Sum(column))
                .values("total")
            )

        return (
            queryset.only("id_area", "geom_4326")
            .annotate(
                counts=total("counts"),
                count_segment=total("count_segment"),
                count_presence=total("count_presence"),
            )
            .order_by("id_area")
        )

    def compute_scores(self, area_ids):
        """``{score name: {id_area: value}}`` for the requested scores."""
        rows = self.counts.filter(id_area__in=area_ids)
        try:
            return {
                name: SCORES[name].compute_from(
                    rows, source_weights=self.params.get("source_weights")
                )
                for name in sorted(self.params.get("scores", ()))
            }
        except ValueError as error:
            raise serializers.ValidationError({"source_weights": [str(error)]})

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        scores = self.compute_scores([area.id_area for area in page])
        serializer = self.get_serializer(page, many=True, context={
            **self.get_serializer_context(), "scores": scores,
        })
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        area = self.get_object()
        serializer = self.get_serializer(area, context={
            **self.get_serializer_context(), "scores": self.compute_scores([area.id_area]),
        })
        return Response(serializer.data)
