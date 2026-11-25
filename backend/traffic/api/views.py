import hashlib
import json
import math
from functools import cached_property

from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_gis.filters import InBBoxFilter

from commons.api.geo import GeoJsonLimitOffsetPagination, GeoViewSet, ReadOnlyViewSet
from commons.models import DataSource, data_version
from ref_geo.models import LArea
from workshop2026.processing.score import (
    SCORES,
    counts_by_area,
    counts_version,
    scored_rows,
    CazalisFrequentationScore,
    BasicFrequentationScore,
)

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
        # Raw data: not the objects of a source hiding it (scores still use them).
        queryset = super().get_queryset().shown()
        return queryset if self.is_geojson() else queryset.defer("geom")


class CountingMeasureViewSet(ReadOnlyViewSet):
    # Unique order, so that pages do not skip or repeat measures.
    queryset = CountingMeasure.objects.select_related("unit", "practice").order_by(
        "counting_object_id", "start_datetime", "id"
    )
    serializer_class = CountingMeasureSerializer
    filterset_class = CountingMeasureFilter

    def get_queryset(self):
        return super().get_queryset().filter(
            counting_object__in=CountingObject.objects.shown().values("id")
        )
    ordering_fields = ("id", "start_datetime", "end_datetime", "count")


@extend_schema_view(
    list=extend_schema(parameters=[AreasQuerySerializer]),
    retrieve=extend_schema(parameters=[AreasQuerySerializer]),
)
class AreasViewSet(viewsets.ReadOnlyModelViewSet):
    """Counts and scores per grid cell (ref_geo ``area_type``, "M1" 1 km by default), as GeoJSON.

    Only the cells with measures matching ``source`` and the period
    ``date_from`` / ``date_to`` (YYYY-MM-DD, both included, on the start of
    the measures), and ``months`` of every year (e.g. 12, 1, 2: the winters).
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
            months=self.params.get("months"),
            area_type=self.area_type,
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # OpenAPI schema generation
            return LArea.objects.none()
        return (
            LArea.objects.filter(
                type__type_code=self.area_type,
                id_area__in=self.measures.values("id_area"),
            )
            .only("id_area", "geom_4326")
            .order_by("id_area")
        )

    @cached_property
    def estimate(self):
        """BTA estimate of the "cazalis" weights (``weights``, ``correlations``,
        ``counters``), or None when the weights are given or the score is not requested.
        """
        if self.params.get("source_weights") is None and "cazalis" in self.params.get(
            "scores", ()
        ):
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
                details["cazalis"]["source_correlations"] = self.estimate[
                    "correlations"
                ]
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
        scores = self.params.get("scores", ())
        if "synthesis" in scores:
            # Also depends on the observations: changes with each import.
            version = f"{version}:{data_version()}"
        filters = (
            sorted(scores),
            sorted(self.params.get("source") or ()),
            str(self.params.get("date_from")),
            str(self.params.get("date_to")),
            sorted(self.params.get("months") or ()),
            self.area_type,
            sorted((self.source_weights or {}).items()),
            self.params.get("synthesis_threshold"),
        )
        return (
            f"area-scores:{version}:{hashlib.sha1(repr(filters).encode()).hexdigest()}"
        )

    def compute_scores(self, measures):
        """``{score name: {id_area: value}}`` for the requested scores."""
        key = self.scores_cache_key()
        scores = cache.get(key) if key else None
        if scores is None:
            scores = {}
            # "synthesis" last: it reuses the "cazalis" scores when they are requested too.
            names = sorted(
                self.params.get("scores", ()),
                key=lambda name: (name == "synthesis", name),
            )
            try:
                for name in names:
                    scores[name] = SCORES[name].compute_from(
                        measures,
                        source_weights=self.source_weights,
                        area_type=self.area_type,
                        synthesis_threshold=self.params.get("synthesis_threshold"),
                        cazalis=scores.get("cazalis"),
                    )
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
        return self.get_serializer(
            areas if many else areas[0], many=many, context=context
        )

    def response_cache_key(self):
        """Key of this list response (its full URL), or None while the precomputed counts are stale.

        The data only changes at an import, which changes the data version: a whole
        page is cached, so the next visitors get the cells without any computation.
        """
        version = counts_version()
        if version is None:
            return None
        url = self.request.build_absolute_uri()
        return f"area-response:{version}:{hashlib.sha1(url.encode()).hexdigest()}"

    def with_source_weights(self, response):
        """Add the weights used by the "cazalis" score to the response."""
        if "cazalis" in self.params.get("scores", ()):
            response.data["source_weights"] = self.source_weights
        return response

    def list(self, request, *args, **kwargs):
        key = self.response_cache_key()
        data = cache.get(key) if key else None
        if data is None:
            page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
            data = self.with_source_weights(
                self.get_paginated_response(self.serialize(page, many=True).data)
            ).data
            if key:
                # Expires only to free the memory of the old data versions.
                cache.set(key, data, timeout=7 * 24 * 3600)
        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        return self.with_source_weights(
            Response(self.serialize([self.get_object()], many=False).data)
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
                {
                    "detail": "bbox must be west,south,east,north within a 2.5-degree extent."
                },
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
                if any(
                    not math.isfinite(weight) or weight < 0
                    for weight in weights.values()
                ):
                    raise ValueError
            except (TypeError, ValueError, json.JSONDecodeError):
                return Response(
                    {
                        "detail": "weights must be a JSON object of non-negative numbers."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                scores = CazalisFrequentationScore.compute(
                    geom_ids=area_ids,
                    source_weights=weights,
                )
            except ValueError as error:
                return Response(
                    {"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST
                )

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
