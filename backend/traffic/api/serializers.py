from rest_framework import serializers
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "code", "label"]


class CountingObjectTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountingObjectType
        fields = ["id", "code", "label"]


class CountingObjectSerializer(GeoFeatureModelSerializer):
    """GeoJSON Feature : `geom` devient la géométrie, le reste va dans `properties`."""

    first_data = serializers.DateTimeField(read_only=True)
    latest_data = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CountingObject
        geo_field = "geom"
        fields = [
            "id",
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
            "id",
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

class GeometrySearchSerializer(serializers.Serializer):
    PREDICATES = ("within", "intersects")

    geometry = GeometryField()
    predicate = serializers.ChoiceField(choices=PREDICATES, default="intersects")
