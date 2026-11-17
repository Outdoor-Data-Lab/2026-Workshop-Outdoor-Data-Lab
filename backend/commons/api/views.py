from rest_framework import viewsets

from ..models import (
DataSource,
DataImport
)
from .serializers import (
DataImportSerializer,
DataSourceSerializer
)

class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = DataSource.objects.order_by("id_source")
    serializer_class = DataSourceSerializer

class DataImportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DataImport.objects.order_by("date_import")
    serializer_class = DataImportSerializer
