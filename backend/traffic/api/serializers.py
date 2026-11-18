from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from commons.api.geo import code_field

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


COUNTING_OBJECT_FIELDS = [
    "id",
    "uuid",
    "external_id",
    "type_code",
    "source_code",
    "origin_code",
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


class CountingObjectSerializer(serializers.ModelSerializer):
    type_code = code_field("type")
    source_code = code_field("source")
    origin_code = code_field("origin")
    first_data = serializers.DateTimeField(read_only=True)
    latest_data = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CountingObject
        fields = COUNTING_OBJECT_FIELDS


class CountingObjectGeoSerializer(GeoFeatureModelSerializer, CountingObjectSerializer):
    """``?format=geojson``: ``geom`` becomes the geometry, the rest the properties."""

    class Meta:
        model = CountingObject
        geo_field = "geom"
        fields = [*COUNTING_OBJECT_FIELDS, "geom"]


class CountingMeasureSerializer(serializers.ModelSerializer):
    unit_code = code_field("unit")
    practice_code = code_field("practice")

    class Meta:
        model = CountingMeasure
        fields = [
            "id",
            "counting_object",
            "external_id",
            "start_datetime",
            "end_datetime",
            "count",
            "unit_code",
            "practice_code",
            "date_create",
            "date_update",
            "processed",
        ]
