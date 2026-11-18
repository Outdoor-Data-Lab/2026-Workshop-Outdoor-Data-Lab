from functools import cached_property

from django.db.models import OuterRef, Subquery, Sum
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework_gis.pagination import GeoJsonPagination

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)
from .serializers import (
    AreaCountsSerializer,
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


@extend_schema_view(
    list=extend_schema(parameters=[AreasQuerySerializer]),
    retrieve=extend_schema(parameters=[AreasQuerySerializer]),
)
class AreasViewSet(viewsets.ReadOnlyModelViewSet):
    """Counts and scores per 1 km grid cell (ref_geo "M1"), as GeoJSON.

    Only the cells with measures matching the filters (source, year, month,
    bbox). Properties: ``counts``, ``count_segment``, ``count_presence`` and
    ``score`` (``{score name: value}`` for the requested ``scores``).
    Geometry in WGS84. Scores are computed for the cells of the page only.
    """

    serializer_class = AreaCountsSerializer
    lookup_field = "id_area"
    pagination_class = GeoJsonPagination

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
        if "bbox" in self.params:
            queryset = queryset.filter(
                geom__intersects=self.params["bbox"].transform(2154, clone=True)
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
        source_weights = self.params.get("source_weights")
        if "cazalis" in self.params.get("scores", ()) and source_weights is None:
            source_weights = SCORES["cazalis"].calculate_source_weights()
        try:
            scores = {
                name: SCORES[name].compute_from(
                    rows, source_weights=source_weights
                )
                for name in sorted(self.params.get("scores", ()))
            }
        except ValueError as error:
            raise serializers.ValidationError({"source_weights": [str(error)]})
        return scores, source_weights

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        scores, source_weights = self.compute_scores([area.id_area for area in page])
        serializer = self.get_serializer(page, many=True, context={
            **self.get_serializer_context(), "scores": scores,
        })
        response = self.get_paginated_response(serializer.data)
        if "cazalis" in self.params.get("scores", ()):
            response.data["source_weights"] = source_weights
        return response

    def retrieve(self, request, *args, **kwargs):
        area = self.get_object()
        scores, source_weights = self.compute_scores([area.id_area])
        serializer = self.get_serializer(area, context={
            **self.get_serializer_context(), "scores": scores,
        })
        response = Response(serializer.data)
        if "cazalis" in self.params.get("scores", ()):
            response.data["source_weights"] = source_weights
        return response
