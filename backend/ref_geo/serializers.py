from rest_framework import serializers
from rest_framework_gis.fields import GeometrySerializerMethodField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

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


class BibAreasTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BibAreasType
        fields = "__all__"


class BibLinearsTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BibLinearsType
        fields = "__all__"


class BibPointsTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BibPointsType
        fields = "__all__"


class LAreaSerializer(serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LArea
        exclude = ("geom", "centroid", "geom_4326", "type")


class LLinearSerializer(serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LLinear
        exclude = ("geom", "geojson_4326", "type")


class LPointSerializer(serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LPoint
        exclude = ("geom", "geojson_4326", "type")


# GeoJSON variants (``?format=geojson``), geometry in WGS84.


class LAreaGeoSerializer(GeoFeatureModelSerializer):
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    class Meta:
        model = LArea
        geo_field = "geom_4326"
        exclude = ("geom", "centroid", "type")


class _Wgs84Mixin(GeoFeatureModelSerializer):
    """Native geometry is Lambert-93: reproject to WGS84 for output."""

    type_code = serializers.CharField(source="type.type_code", read_only=True)
    geometry = GeometrySerializerMethodField()

    def get_geometry(self, obj):
        return obj.geom.transform(4326, clone=True) if obj.geom else None


class LLinearGeoSerializer(_Wgs84Mixin):
    class Meta:
        model = LLinear
        geo_field = "geometry"
        exclude = ("geom", "geojson_4326", "type")


class LPointGeoSerializer(_Wgs84Mixin):
    class Meta:
        model = LPoint
        geo_field = "geometry"
        exclude = ("geom", "geojson_4326", "type")


class LiMunicipalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LiMunicipality
        fields = "__all__"


class LiGridSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiGrid
        fields = "__all__"


class TLinearGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TLinearGroup
        fields = ("id_group", "name", "code")
