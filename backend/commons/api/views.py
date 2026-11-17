from rest_framework import viewsets

from ..models import (
    DataSource,
    DataImport, PracticeCategory
)
from .serializers import (
    DataImportSerializer,
    DataSourceSerializer, PracticeCategorySerializer
)

class PracticeCategoryViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = PracticeCategory.objects.order_by("id")
    serializer_class = PracticeCategorySerializer

class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = DataSource.objects.order_by("id")
    serializer_class = DataSourceSerializer

class DataImportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataImport.objects.order_by("date_import")
    serializer_class = DataImportSerializer
