import hashlib
from functools import cached_property

from django.conf import settings
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework_gis.filters import InBBoxFilter

from commons.api.geo import GeoJsonLimitOffsetPagination, GeoViewSet, ReadOnlyViewSet
from ref_geo.models import LArea
from workshop2026.processing.score import SCORES, counts_by_area, counts_version, scored_rows

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)
from .filters import CountingMeasureFilter, CountingObjectFilter, TrafficAreaFilter
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
    """Counts and scores per grid cell (ref_geo ``area_type``, "M1" 1 km by default), as GeoJSON.

    Only the cells with measures matching ``source`` and the period
    ``date_from`` / ``date_to`` (YYYY-MM-DD, both included, on the start of
    the measures).
    Properties: ``counts``, ``count_segment``, ``count_presence``, ``sources``
    (counts per data source, absolute or relative) and ``score``
    (``{score name: value}`` for the requested ``scores``). Geometry in WGS84.
    Scores are computed for the cells of the page only.

    Spatial filters on the cells, as in ref_geo: ``bbox``, ``point``,
    ``intersects``, ``within``, ``contains`` (LAreaFilter, on the indexed
    Lambert-93 geometry) and ``in_bbox`` (rest_framework_gis); ``area_id``:
    cells intersecting this ref_geo area. Pagination:
    ``limit`` / ``offset``.
    """

    serializer_class = AreaCountsSerializer
    lookup_field = "id_area"
    pagination_class = GeoJsonLimitOffsetPagination
    filter_backends = [DjangoFilterBackend, InBBoxFilter]
    filterset_class = TrafficAreaFilter
    # InBBoxFilter builds its box without an SRID: it must target the WGS84 column.
    bbox_filter_field = "geom_4326"
    bbox_filter_include_overlapping = True

    @cached_property
    def params(self):
        serializer = AreasQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @property
    def area_type(self):
        return self.params.get("area_type") or settings.DEFAULT_GRID_AREA_TYPE

    @cached_property
    def measures(self):
        """Rows matching source and period (see ``scored_rows``): the precomputed
        counts per (cell, source, day) when fresh, else one row per (measure, cell)."""
        return scored_rows(
            sources=self.params.get("source"),
            date_from=self.params.get("date_from"),
            date_to=self.params.get("date_to"),
            area_type=self.area_type,
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI schema generation
            return LArea.objects.none()
        return (
            LArea.objects.filter(
                type__type_code=self.area_type, id_area__in=self.measures.values("id_area")
            )
            .only("id_area", "geom_4326")
            .order_by("id_area")
        )

    @cached_property
    def estimate(self):
        """BTA estimate of the "cazalis" weights (``weights``, ``correlations``,
        ``counters``), or None when the weights are given or the score is not requested."""
        if self.params.get("source_weights") is None and "cazalis" in self.params.get("scores", ()):
            return SCORES["cazalis"].cached_estimate()
        return None

    @cached_property
    def source_weights(self):
        """Weights of the "cazalis" score: given, or estimated (BTA) when omitted."""
        if self.estimate is not None:
            return self.estimate["weights"]
        return self.params.get("source_weights")

    @cached_property
    def score_details(self):
        """``{score name: dict}``: what goes next to the value of that score in
        every cell (``score[name]`` becomes ``{"score": value, **dict}``).

        "cazalis": the weight of each source (``source_weights``) and, when
        estimated, its correlation with the eco-counters (``source_correlations``:
        ``{source id: {"r": Pearson's r or null, "counters": n}}``) and the
        number of eco-counters used (``reference_counters``).
        """
        details = {}
        if "cazalis" in self.params.get("scores", ()):
            details["cazalis"] = {"source_weights": self.source_weights}
            if self.estimate is not None:
                details["cazalis"]["source_correlations"] = self.estimate["correlations"]
                details["cazalis"]["reference_counters"] = self.estimate["counters"]
        return details

    def scores_cache_key(self):
        """Key of the scores of this request, or None while the precomputed counts are stale.

        The scores are standardised over every matching cell, so each page of
        the same request has the same ones: they are computed once. The key
        holds what they depend on: the filters, the weights and the data version.
        """
        version = counts_version()
        if version is None:
            return None
        filters = (
            sorted(self.params.get("scores", ())),
            sorted(self.params.get("source") or ()),
            str(self.params.get("date_from")),
            str(self.params.get("date_to")),
            self.area_type,
            sorted((self.source_weights or {}).items()),
        )
        return f"area-scores:{version}:{hashlib.sha1(repr(filters).encode()).hexdigest()}"

    def compute_scores(self, measures):
        """``{score name: {id_area: value}}`` for the requested scores."""
        key = self.scores_cache_key()
        scores = cache.get(key) if key else None
        if scores is None:
            try:
                scores = {
                    name: SCORES[name].compute_from(measures, source_weights=self.source_weights)
                    for name in sorted(self.params.get("scores", ()))
                }
            except ValueError as error:
                raise serializers.ValidationError({"source_weights": [str(error)]})
            if key:
                cache.set(key, scores, timeout=None)
        return scores

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
            "score_details": self.score_details,
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
