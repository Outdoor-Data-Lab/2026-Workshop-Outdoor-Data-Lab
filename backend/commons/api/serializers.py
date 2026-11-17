from rest_framework import serializers

from ..models import (
    DataImport,
    DataSource
)

class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id_source", "code_source", "source"]

class DataImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataImport
        fields = ["id_import", "date_import", "source", "line_numbers", "error_numbers"]


