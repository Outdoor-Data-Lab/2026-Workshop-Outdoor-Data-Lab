from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework_gis.pagination import GeoJsonPagination

from ..models import (
    Activity,
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)
from .serializers import (
    ActivitySerializer,
    CountingMeasureSerializer,
    CountingObjectSerializer,
    CountingObjectTypeSerializer,
    UnitSerializer,
)

class UnitViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Unit.objects.order_by("id_unit")
    serializer_class = UnitSerializer


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Activity.objects.order_by("id_activity")
    serializer_class = ActivitySerializer


class CountingObjectTypeViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CountingObjectType.objects.order_by("id_type")
    serializer_class = CountingObjectTypeSerializer


class CountingObjectViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CountingObject.objects.with_data_range().order_by("date_create")
    serializer_class = CountingObjectSerializer
    pagination_class = GeoJsonPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type"]


class CountingMeasureViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = CountingMeasure.objects.order_by("counting_object_id")
    serializer_class = CountingMeasureSerializer
    pagination_class = PageNumberPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["counting_object"]