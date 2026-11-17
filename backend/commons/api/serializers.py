from rest_framework import serializers

from ..models import (
    DataImport,
    DataSource, PracticeCategory
)


class PracticeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeCategory
        fields = ["code", "label"]


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "code", "label"]


class DataImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataImport
        fields = ["id", "date_import", "source", "line_numbers", "error_numbers"]
