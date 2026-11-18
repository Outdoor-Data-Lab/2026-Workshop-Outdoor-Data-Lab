from django_filters import rest_framework as filters

from commons.api.geo import SpatialFilterSet

from ..models import CountingMeasure, CountingObject


class CountingObjectFilter(SpatialFilterSet):
    type_code = filters.CharFilter(field_name="type__code")
    source_code = filters.CharFilter(field_name="source__code")
    origin_code = filters.CharFilter(field_name="origin__code")

    class Meta:
        model = CountingObject
        fields = []


class CountingMeasureFilter(filters.FilterSet):
    unit_code = filters.CharFilter(field_name="unit__code")
    practice_code = filters.CharFilter(field_name="practice__code")

    class Meta:
        model = CountingMeasure
        fields = ["counting_object"]
