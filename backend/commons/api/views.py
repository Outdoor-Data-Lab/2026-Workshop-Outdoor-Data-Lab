from ..models import DataImport, DataSource, Practice
from .filters import DataImportFilter, PracticeFilter
from .geo import ReadOnlyViewSet
from .serializers import DataImportSerializer, DataSourceSerializer, PracticeSerializer


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
