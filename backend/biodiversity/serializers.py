from rest_framework import serializers
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ref_geo.models import LArea


class TaxonStatusAreaSerializer(GeoFeatureModelSerializer):
    """GeoJSON representation of an area and its taxon status counters."""

    geom_4326 = GeometryField(read_only=True)
    type_code = serializers.CharField(source="type.type_code", read_only=True)
    protected_taxa_count = serializers.IntegerField(read_only=True)
    threatened_taxa_count = serializers.IntegerField(read_only=True)
    protected_or_threatened_taxa_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = LArea
        geo_field = "geom_4326"
        fields = (
            "id_area",
            "area_code",
            "area_name",
            "type_code",
            "geom_4326",
            "protected_taxa_count",
            "threatened_taxa_count",
            "protected_or_threatened_taxa_count",
        )
