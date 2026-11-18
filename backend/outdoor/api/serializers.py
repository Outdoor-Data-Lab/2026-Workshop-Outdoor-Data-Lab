
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ref_geo.models import LArea
from ..models import Offer


class OfferSerializer(serializers.ModelSerializer):
    """Serializer for Offer model (JSON format)."""

    practice_label = serializers.CharField(source='practice.label', read_only=True)
    source_label = serializers.CharField(source='source.label', read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id',
            'uuid',
            'external_id',
            'practice',
            'practice_label',
            'source',
            'source_label',
            'date_create',
            'date_update',
            'geom',
        ]
        read_only_fields = ['id', 'uuid', 'date_create', 'date_update']


class OfferGeoSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for Offer model."""
    practice_label = serializers.CharField(source='practice.label', read_only=True)
    source_label = serializers.CharField(source='source.label', read_only=True)

    class Meta:
        model = Offer
        geo_field = 'geom'
        fields = [
            'id',
            'uuid',
            'external_id',
            'practice',
            'practice_label',
            'source',
            'source_label',
            'date_create',
            'date_update',
        ]
        read_only_fields = ['id', 'uuid', 'date_create', 'date_update']


class LAreaWithOffersCountSerializer(serializers.ModelSerializer):
    """Serializer for areas with offers count."""
    type_code = serializers.CharField(source="type.type_code", read_only=True)
    offers_count = serializers.SerializerMethodField()

    class Meta:
        model = LArea
        exclude = ("geom", "centroid", "geom_4326", "type")

    def get_offers_count(self, obj):
        """Return the count of offers within this area."""
        from django.contrib.gis.geos import GEOSGeometry
        from outdoor.models import Offer

        if obj.geom_4326:
            # Count offers that intersect with this area
            return Offer.objects.filter(geom__intersects=obj.geom_4326).count()
        return 0
