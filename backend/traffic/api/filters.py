from django.core.exceptions import ValidationError
from django_filters import rest_framework as filters

from commons.api.geo import SpatialFilterSet
from ref_geo.models import LArea
from workshop2026.api.mixins import AreaFilterSet

from ..models import CountingMeasure, CountingObject


class CountingObjectFilter(AreaFilterSet, SpatialFilterSet):
    type_code = filters.CharFilter(field_name="type__code")
    source_code = filters.CharFilter(field_name="source__code")
    origin_code = filters.CharFilter(field_name="origin__code")
    area_code = filters.CharFilter(method="filter_by_area_code")
    area_id = filters.NumberFilter(method="filter_by_area_id")
    filterset_class = AreaFilterSet

    class Meta:
        model = CountingObject
        fields = []


class CountingMeasureFilter(filters.FilterSet):
    unit_code = filters.CharFilter(field_name="unit__code")
    practice_code = filters.CharFilter(field_name="practice__code")

    class Meta:
        model = CountingMeasure
        fields = ["counting_object"]
