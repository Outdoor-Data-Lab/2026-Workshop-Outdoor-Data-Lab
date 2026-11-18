from django.db.models import Count
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from ref_geo.models import LArea
from workshop2026.api.mixins import DynamicFieldsMixin
from ..models import Offer


OFFER_FIELDS = [
    "id", "uuid", "external_id",
    "practice", "practice_label",
    "source", "source_label",
    "date_create", "date_update",
]


class OfferLabelsMixin(serializers.Serializer):
    practice_label = serializers.CharField(source="practice.label", read_only=True)
    source_label = serializers.CharField(source="source.label", read_only=True)


class OfferSerializer(DynamicFieldsMixin, OfferLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = OFFER_FIELDS + ["geom"]
        read_only_fields = ["id", "uuid", "date_create", "date_update"]


class OfferGeoSerializer(DynamicFieldsMixin, OfferLabelsMixin, GeoFeatureModelSerializer):
    class Meta(OfferSerializer.Meta):
        geo_field = "geom"
        fields = OFFER_FIELDS


class OffersCountMixin(serializers.Serializer):
    """Nombre d'offres qui intersectent la géométrie de la zone."""

    offers_count = serializers.SerializerMethodField()
    type_code = serializers.CharField(source="type.type_code", read_only=True)

    @staticmethod
    def _offers(obj):
        if not obj.geom_4326:
            return Offer.objects.none()
        return Offer.objects.filter(geom__intersects=obj.geom_4326)

    def get_offers_count(self, obj):
        return self._offers(obj).count()


class OffersCountByPracticeMixin(OffersCountMixin):
    """Ajoute le détail par type d'activité."""

    offers_count_by_practice = serializers.SerializerMethodField()

    def get_offers_count_by_practice(self, obj):
        rows = (
            self._offers(obj)
            .values("practice__code", "practice__label")
            .annotate(count=Count("id"))
            .order_by("practice__code")
        )
        return [
            {
                "practice_code": r["practice__code"],
                "practice_label": r["practice__label"],
                "count": r["count"],
            }
            for r in rows
        ]


class LAreaMeta:
    model = LArea
    exclude = ("geom", "centroid", "geom_4326", "type")


class LAreaGeoMeta:
    model = LArea
    geo_field = "geom_4326"
    exclude = ("geom", "centroid", "type")


class LAreaWithOffersCountSerializer(DynamicFieldsMixin, OffersCountMixin, serializers.ModelSerializer):
    Meta = LAreaMeta


class LAreaGeoWithOffersCountSerializer(DynamicFieldsMixin,OffersCountMixin, GeoFeatureModelSerializer):
    Meta = LAreaGeoMeta


class LAreaWithOffersCountAndByPracticeSerializer(DynamicFieldsMixin, gfjOffersCountByPracticeMixin, serializers.ModelSerializer):
    Meta = LAreaMeta


class LAreaGeoWithOffersCountAndByPracticeSerializer(
    OffersCountByPracticeMixin, GeoFeatureModelSerializer
):
    Meta = LAreaGeoMeta