from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
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
    CountingMeasureSerializer,
    CountingObjectSerializer,
    CountingObjectTypeSerializer,
    UnitSerializer, GeometrySearchSerializer,
)

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