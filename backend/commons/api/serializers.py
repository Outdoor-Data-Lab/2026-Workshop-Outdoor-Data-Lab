from rest_framework import serializers

from ..models import DataImport, DataSource, ExternalLayer, Practice
from .geo import code_field


class PracticeSerializer(serializers.ModelSerializer):
    parent_code = code_field("parent")

    class Meta:
        model = Practice
        fields = ["id", "code", "label", "parent_code"]


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "code", "label"]


class DataImportSerializer(serializers.ModelSerializer):
    source_code = code_field("source")

    class Meta:
        model = DataImport
        fields = ["id", "date_import", "source_code", "line_numbers", "error_numbers"]


class ExternalLayerSerializer(serializers.ModelSerializer):
    colors = serializers.DictField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = ExternalLayer
        fields = [
            "id", "label", "url", "description",
            "properties", "color", "color_property", "colors",
        ]
        read_only_fields = fields  # all always present in the schema
