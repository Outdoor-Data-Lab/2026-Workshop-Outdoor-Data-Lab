from django_filters import rest_framework as filters

from workshop2026.api.mixins import AreaFilterSet
from ..models import Offer


class OfferFilter(AreaFilterSet, filters.FilterSet):
    """Filter for Offer model with practice, source, uuid, date_create, external_id and areas."""
    practice = filters.NumberFilter(field_name='practice_id', lookup_expr='exact')
    source = filters.NumberFilter(field_name='source_id', lookup_expr='exact')
    uuid = filters.CharFilter(field_name='uuid', lookup_expr='exact')
    external_id = filters.CharFilter(field_name='external_id', lookup_expr='icontains')

    date_from = filters.DateTimeFilter(field_name='date_create', lookup_expr='gte')
    date_to = filters.DateTimeFilter(field_name='date_create', lookup_expr='lte')

    class Meta:
        model = Offer
        fields = ['practice', 'source', 'uuid', 'external_id', 'date_from', 'date_to']
