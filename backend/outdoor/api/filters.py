from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from ref_geo.filters import LAreaFilter
from ref_geo.models import LArea
from workshop2026.api.mixins import AreaFilterSet
from ..models import Offer


class LAreaCountFilter(LAreaFilter):
    """Filter for LArea that returns areas intersecting with a given area code,
    excluding other areas with the same type_code."""

    area_code = filters.CharFilter(
        method="filter_by_area_code",
        label="Area code",
        help_text="Filter areas that intersect with the given area code (e.g., '05')"
    )

    def filter_by_area_code(self, queryset, name, value):
        """Filter areas that intersect with the specified area code.
        Includes the exact area found AND other areas that intersect,
        but excludes other areas with the same type_code."""
        try:
            parent_area = LArea.objects.get(area_code=value)
            return queryset.filter(
                Q(area_code=value) |  Q(geom_4326__within=parent_area.geom_4326)
            )
        except LArea.DoesNotExist:
            raise ValidationError(
                {"area_code": f"Area with code '{value}' does not exist."}
            )

    class Meta:
        model = LArea
        fields = ["enable"]

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
