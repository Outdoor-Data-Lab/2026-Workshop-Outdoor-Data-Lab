from rest_framework import serializers
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from workshop2026.api.mixins import DynamicFieldsMixin
from .models import (
    BibAreasType,
    BibLinearsType,
    BibPointsType,
    LArea,
    LiGrid,
    LiMunicipality,
    LLinear,
    LPoint,
    TLinearGroup,
)


class BibAreasTypeSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = BibAreasType
        fields = "__all__"


class BibLinearsTypeSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = BibLinearsType
        fields = "__all__"


class BibPointsTypeSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = BibPointsType
        fields = "__all__"


class LAreaSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LArea
        exclude = ("geom", "centroid", "geom_4326", "type")


class LLinearSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LLinear
        exclude = ("geom", "geojson_4326", "type")


class LPointSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LPoint
        exclude = ("geom", "geojson_4326", "type")


# GeoJSON variants (``?format=geojson``), geometry in WGS84.


class LAreaGeoSerializer(DynamicFieldsMixin, GeoFeatureModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LArea
        geo_field = "geom_4326"
        exclude = ("geom", "centroid", "type")


class LLinearGeoSerializer(DynamicFieldsMixin, GeoFeatureModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)
    # annotated in SQL by the viewset (Transform(geom, 4326))
    geom_4326 = GeometryField(read_only=True)

    class Meta:
        model = LLinear
        geo_field = "geom_4326"
        exclude = ("geom", "geojson_4326", "type")


class LPointGeoSerializer(DynamicFieldsMixin, GeoFeatureModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)
    geom_4326 = GeometryField(read_only=True)

    class Meta:
        model = LPoint
        geo_field = "geom_4326"
        exclude = ("geom", "geojson_4326", "type")


class LiMunicipalitySerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = LiMunicipality
        fields = "__all__"


class LiGridSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = LiGrid
        fields = "__all__"


class TLinearGroupSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = TLinearGroup
        fields = ("id_group", "name", "code")
