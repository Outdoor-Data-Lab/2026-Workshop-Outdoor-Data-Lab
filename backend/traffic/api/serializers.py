from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ..models import (
    Activity,
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id_unit", "code_unit", "unit"]


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ["id_activity", "code_activity", "activity"]


class CountingObjectTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountingObjectType
        fields = ["id_type", "code_type", "type"]


class CountingObjectSerializer(GeoFeatureModelSerializer):
    """GeoJSON Feature : `geom` devient la géométrie, le reste va dans `properties`."""

    first_data = serializers.DateTimeField(read_only=True)
    latest_data = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CountingObject
        geo_field = "geom"
        id_field = "id_counting_object"
        fields = [
            "id_counting_object",
            "uuid",
            "external_id",
            "type",
            "source",
            "geom",
            "date_create",
            "date_update",
            "installation_date",
            "uninstallation_date",
            "processed",
            "manager",
            "image_url",
            "first_data",
            "latest_data",
        ]


class CountingMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountingMeasure
        fields = [
            "id_measure",
            "counting_object",
            "external_id",
            "start_datetime",
            "end_datetime",
            "count",
            "unit",
            "activity",
            "date_create",
            "date_update",
            "processed",
        ]