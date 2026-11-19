from django.core.exceptions import ValidationError
from django.db.models import Subquery
from django_filters import rest_framework as filters

from rest_framework.exceptions import ValidationError as ApiValidationError

from commons.api.geo import SpatialFilterSet
from ref_geo.filters import LAreaFilter
from ref_geo.models import LArea
from workshop2026.api.mixins import AreaFilterSet

from ..models import CountingMeasure, CountingObject, CountingObjectType


class CountingObjectFilter(AreaFilterSet, SpatialFilterSet):
    type_code = filters.CharFilter(method="filter_by_type_code")
    source_code = filters.CharFilter(field_name="source__code")
    origin_code = filters.CharFilter(field_name="origin__code")
    area_code = filters.CharFilter(method="filter_by_area_code")
    area_id = filters.NumberFilter(method="filter_by_area_id")
    filterset_class = AreaFilterSet

    class Meta:
        model = CountingObject
        fields = []

    def filter_by_type_code(self, queryset, name, value):
        """On ``type_id``, not through a join: PostgreSQL then tests the type before
        the area (``area_id``, ``area_code``), which costs about 1 ms per object
        against a detailed polygon (8 s for the counters of a department, among
        thousands of segments)."""
        type_id = CountingObjectType.objects.filter(code=value).values("id")[:1]
        return queryset.filter(type_id=Subquery(type_id))


class TrafficAreaFilter(LAreaFilter):
    """Grid cells. ``area_id``: cells intersecting this ref_geo area (commune,
    park...), as on the other routes; ``area_code`` stays the cell's own code."""

    area_id = filters.NumberFilter(method="filter_by_area_id")

    def filter_by_area_id(self, queryset, name, value):
        area = LArea.objects.filter(id_area=value).only("geom").first()
        if area is None:
            raise ApiValidationError({"area_id": f"Area with ID '{value}' does not exist."})
        # Lambert-93 on both sides: the GiST index of the cells is used.
        return queryset.filter(geom__intersects=area.geom)


class CountingMeasureFilter(filters.FilterSet):
    unit_code = filters.CharFilter(field_name="unit__code")
    practice_code = filters.CharFilter(field_name="practice__code")

    class Meta:
        model = CountingMeasure
        fields = ["counting_object"]
