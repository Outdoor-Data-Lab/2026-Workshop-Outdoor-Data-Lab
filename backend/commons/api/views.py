from rest_framework.generics import RetrieveAPIView

from ..models import DataImport, DataSource, ExternalLayer, InstanceSettings, Practice
from .filters import DataImportFilter, PracticeFilter
from .geo import ReadOnlyViewSet
from .serializers import (
    DataImportSerializer,
    DataSourceSerializer,
    ExternalLayerSerializer,
    InstanceSettingsSerializer,
    PracticeSerializer,
)


class PracticeViewSet(ReadOnlyViewSet):
    queryset = Practice.objects.select_related("parent").order_by("id")
    serializer_class = PracticeSerializer
    filterset_class = PracticeFilter
    ordering_fields = ("id", "code", "label")


class DataSourceViewSet(ReadOnlyViewSet):
    queryset = DataSource.objects.order_by("id")
    serializer_class = DataSourceSerializer
    filterset_fields = ["code"]
    ordering_fields = ("id", "code", "label")


class DataImportViewSet(ReadOnlyViewSet):
    queryset = DataImport.objects.select_related("source").order_by("date_import")
    serializer_class = DataImportSerializer
    filterset_class = DataImportFilter
    ordering_fields = ("id", "date_import")


class ExternalLayerViewSet(ReadOnlyViewSet):
    queryset = ExternalLayer.objects.order_by("label")
    serializer_class = ExternalLayerSerializer
    ordering_fields = ("id", "label")


class InstanceSettingsView(RetrieveAPIView):
    """Settings of this instance (default area of the map)."""

    serializer_class = InstanceSettingsSerializer

    def get_object(self):
        # No join to ref_geo: the area is read only when set (ref_geo may not be loaded yet).
        return InstanceSettings.load()
