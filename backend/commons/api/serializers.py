from rest_framework import serializers

from ..models import (
    DataImport,
    DataSource, Practice
)


class PracticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Practice
        fields = ["id","code", "label", "parent"]


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "code", "label"]


class DataImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataImport
        fields = ["id", "date_import", "source", "line_numbers", "error_numbers"]
