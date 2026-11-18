from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from commons.api.geo import code_field
from workshop2026.processing.score import SCORES

from ref_geo.models import LArea

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


class AreasQuerySerializer(serializers.Serializer):
    """Query parameters of the areas route."""

    source = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Data source id (repeatable). All sources if omitted.",
    )
    year = serializers.IntegerField(required=False)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)
    scores = serializers.MultipleChoiceField(
        choices=sorted(SCORES),
        required=False,
        help_text="Scores to compute (repeatable).",
    )
    source_weights = serializers.CharField(
        required=False,
        help_text='Weights of the "cazalis" score, as source_id:weight pairs, e.g. "1:2,3:0.5".',
    )

    def validate_source_weights(self, value):
        try:
            pairs = (item.split(":") for item in value.split(",") if item.strip())
            return {int(source): float(weight) for source, weight in pairs}
        except ValueError:
            raise serializers.ValidationError(
                'Expected "source_id:weight,...", e.g. "1:2,3:0.5".'
            )

    def validate(self, data):
        if "cazalis" in data.get("scores", ()) and "source_weights" not in data:
            raise serializers.ValidationError(
                {"source_weights": 'Required by the "cazalis" score.'}
            )
        return data


class AreaCountsSerializer(GeoFeatureModelSerializer):
    """A grid cell with its counts (annotated by AreasViewSet) and its scores
    (``context["scores"]``: ``{score name: {id_area: value}}``)."""

    counts = serializers.IntegerField(read_only=True)
    count_segment = serializers.IntegerField(read_only=True)
    count_presence = serializers.IntegerField(read_only=True)
    score = serializers.SerializerMethodField()

    class Meta:
        model = LArea
        geo_field = "geom_4326"
        id_field = "id_area"
        fields = ["id_area", "geom_4326", "counts", "count_segment", "count_presence", "score"]

    def get_score(self, area) -> dict[str, float]:
        return {
            name: values.get(area.id_area, 0)
            for name, values in self.context.get("scores", {}).items()
        }
