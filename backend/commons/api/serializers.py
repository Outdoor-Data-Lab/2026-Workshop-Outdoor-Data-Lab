from rest_framework import serializers

from workshop2026.api.mixins import DynamicFieldsMixin
from ref_geo.models import LArea

from ..models import DataImport, DataSource, ExternalLayer, InstanceSettings, Practice
from .geo import code_field


class PracticeSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    parent_code = code_field("parent")

    class Meta:
        model = Practice
        fields = ["id", "code", "label", "parent_code"]


class DataSourceSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "code", "label"]


class DataImportSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    source_code = code_field("source")

    class Meta:
        model = DataImport
        fields = ["id", "date_import", "source_code", "line_numbers", "error_numbers"]


class ExternalLayerSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    colors = serializers.DictField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = ExternalLayer
        fields = [
            "id", "label", "url", "description",
            "properties", "label_property", "color", "color_property", "colors",
        ]
        read_only_fields = fields  # all always present in the schema


class AreaSummarySerializer(serializers.ModelSerializer):
    """An area without its geometry, as found by name in ref_geo."""

    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LArea
        fields = ("id_area", "area_name", "area_code", "type_code")


class InstanceSettingsSerializer(serializers.ModelSerializer):
    default_area = AreaSummarySerializer(read_only=True)

    class Meta:
        model = InstanceSettings
        fields = ("default_area",)
