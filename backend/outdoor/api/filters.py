from django_filters import rest_framework as filters
from ref_geo.models import LArea
from rest_framework.exceptions import ValidationError
from ..models import Offer


class OfferFilter(filters.FilterSet):
    """Filter for Offer model with practice, source, uuid, date_create, external_id and areas."""

    practice = filters.NumberFilter(field_name='practice_id', lookup_expr='exact')
    source = filters.NumberFilter(field_name='source_id', lookup_expr='exact')
    uuid = filters.CharFilter(field_name='uuid', lookup_expr='exact')
    external_id = filters.CharFilter(field_name='external_id', lookup_expr='icontains')

    date_from = filters.DateTimeFilter(field_name='date_create', lookup_expr='gte')
    date_to = filters.DateTimeFilter(field_name='date_create', lookup_expr='lte')

    area = filters.NumberFilter(method="filter_by_area")

    class Meta:
        model = Offer
        fields = ['practice', 'source', 'uuid', 'external_id', 'date_from', 'date_to', 'area']

    def filter_by_area(self, queryset, name, value):
        try:
            area = LArea.objects.get(id_area=value)
            return queryset.filter(geom__intersects=area.geom_4326)
        except LArea.DoesNotExist:
            raise ValidationError({"area": f"Area with id {value} does not exist."})