from functools import cached_property

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework_gis.filters import InBBoxFilter

from commons.api.geo import GeoJsonLimitOffsetPagination, GeoViewSet, ReadOnlyViewSet
from ref_geo.filters import LAreaFilter
from ref_geo.models import LArea
from workshop2026.processing.score import SCORES, counts_by_area, measures_queryset

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

    Only the cells with measures matching ``source`` and the period
    ``date_from`` / ``date_to`` (YYYY-MM-DD, both included, on the start of
    the measures).
    Properties: ``counts``, ``count_segment``, ``count_presence``, ``sources``
    (counts per data source, absolute or relative) and ``score``
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
    def measures(self):
        """Measures matching source and period, one row per (measure, cell)."""
        return measures_queryset(
            sources=self.params.get("source"),
            date_from=self.params.get("date_from"),
            date_to=self.params.get("date_to"),
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI schema generation
            return LArea.objects.none()
        return (
            LArea.objects.filter(
                type__type_code="M1", id_area__in=self.measures.values("id_area")
            )
            .only("id_area", "geom_4326")
            .order_by("id_area")
        )

    @cached_property
    def source_weights(self):
        """Weights of the "cazalis" score: given, or estimated (BTA) when omitted."""
        weights = self.params.get("source_weights")
        if weights is None and "cazalis" in self.params.get("scores", ()):
            weights = SCORES["cazalis"].cached_source_weights()
        return weights

    def compute_scores(self, measures):
        """``{score name: {id_area: value}}`` for the requested scores."""
        try:
            return {
                name: SCORES[name].compute_from(measures, source_weights=self.source_weights)
                for name in sorted(self.params.get("scores", ()))
            }
        except ValueError as error:
            raise serializers.ValidationError({"source_weights": [str(error)]})

    def serialize(self, areas, many):
        """Serializer of ``areas`` with the counts of these cells.

        Scores are computed over every cell matching source and period, not
        only ``areas``: the "cazalis" score is standardised across cells, so it
        must not depend on pagination or on the spatial filters.
        """
        measures = self.measures.filter(id_area__in=[area.id_area for area in areas])
        context = {
            **self.get_serializer_context(),
            "counts": counts_by_area(measures),
            "scores": self.compute_scores(self.measures),
        }
        return self.get_serializer(areas if many else areas[0], many=many, context=context)

    def with_source_weights(self, response):
        """Add the weights used by the "cazalis" score to the response."""
        if "cazalis" in self.params.get("scores", ()):
            response.data["source_weights"] = self.source_weights
        return response

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.with_source_weights(
            self.get_paginated_response(self.serialize(page, many=True).data)
        )

    def retrieve(self, request, *args, **kwargs):
        return self.with_source_weights(
            Response(self.serialize([self.get_object()], many=False).data)
        )
