from rest_framework import serializers

from workshop2026.api.mixins import DynamicFieldsMixin
from ..models import DataImport, DataSource, Practice
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
