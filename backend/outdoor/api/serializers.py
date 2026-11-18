
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ref_geo.models import LArea
from ..models import Offer


class OfferSerializer(serializers.ModelSerializer):

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

class OffersCountMixin(serializers.Serializer):
    """Ajoute le nombre d'offres qui intersectent la géométrie de la zone."""

    offers_count = serializers.SerializerMethodField()
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    def get_offers_count(self, obj):
        if not obj.geom_4326:
            return 0
        return Offer.objects.filter(geom__intersects=obj.geom_4326).count()


class LAreaWithOffersCountSerializer(OffersCountMixin, serializers.ModelSerializer):

    class Meta:
        model = LArea
        exclude = ("geom", "centroid", "geom_4326", "type")


class LAreaGeoWithOffersCountSerializer(OffersCountMixin, GeoFeatureModelSerializer):

    class Meta:
        model = LArea
        geo_field = "geom_4326"
        exclude = ("geom", "centroid", "type")