from math import isfinite

from django.conf import settings

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from commons.api.geo import code_field
from workshop2026.api.mixins import DynamicFieldsMixin
from workshop2026.processing.score import SCORES

from ref_geo.models import LArea

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)


class UnitSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "code", "label"]


class CountingObjectTypeSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
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


class CountingObjectSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
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


class CountingMeasureSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
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


class AreasQuerySerializer(DynamicFieldsMixin, serializers.Serializer):
    """Query parameters of the areas route."""

    source = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Data source id (repeatable). All sources if omitted.",
    )
    date_from = serializers.DateField(
        required=False, help_text="First day of the period (YYYY-MM-DD), included."
    )
    date_to = serializers.DateField(
        required=False, help_text="Last day of the period (YYYY-MM-DD), included."
    )
    scores = serializers.MultipleChoiceField(
        choices=sorted(SCORES),
        required=False,
        help_text="Scores to compute (repeatable).",
    )
    area_type = serializers.ChoiceField(
        choices=settings.AREA_TYPES,
        required=False,
        help_text=f"Grid (ref_geo type_code). Default: {settings.DEFAULT_AREA_TYPE}.",
    )
    source_weights = serializers.CharField(
        required=False,
        help_text='Weights of the "cazalis" score, as source_id:weight pairs, e.g. "1:2,3:0.5".',
    )

    def validate_source_weights(self, value):
        try:
            pairs = (item.split(":") for item in value.split(",") if item.strip())
            weights = {int(source): float(weight) for source, weight in pairs}
        except ValueError:
            raise serializers.ValidationError('Expected "source_id:weight,...", e.g. "1:2,3:0.5".')
        if not all(isfinite(weight) for weight in weights.values()):
            raise serializers.ValidationError("Weights must be finite numbers.")
        return weights

    def validate(self, data):
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise serializers.ValidationError({"date_to": "Must not be before date_from."})
        return data


class AreaCountsSerializer(DynamicFieldsMixin, GeoFeatureModelSerializer):
    """A grid cell with its counts (``context["counts"]``:
    ``{id_area: {"counts", "count_segment", "count_presence"}}``) and its scores
    (``context["scores"]``: ``{score name: {id_area: value}}``), both computed
    by AreasViewSet.

    A score with details (``context["score_details"]``: ``{score name: dict}``)
    is an object: ``{"score": value, **details}``, else the bare value. For
    "cazalis": ``source_weights`` and, when estimated, ``source_correlations``
    and ``reference_counters``."""

    counts = serializers.SerializerMethodField()
    count_segment = serializers.SerializerMethodField()
    count_presence = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()

    class Meta:
        model = LArea
        geo_field = "geom_4326"
        id_field = "id_area"
        fields = ["id_area", "geom_4326", "counts", "count_segment", "count_presence", "score"]

    def _count(self, area, column):
        return self.context.get("counts", {}).get(area.id_area, {}).get(column, 0)

    def get_counts(self, area) -> int:
        return self._count(area, "counts")

    def get_count_segment(self, area) -> int:
        return self._count(area, "count_segment")

    def get_count_presence(self, area) -> int:
        return self._count(area, "count_presence")

    def get_score(self, area) -> dict[str, float | dict]:
        details = self.context.get("score_details", {})
        result = {}
        for name, values in self.context.get("scores", {}).items():
            value = values.get(area.id_area, 0)
            result[name] = {"score": value, **details[name]} if details.get(name) else value
        return result
