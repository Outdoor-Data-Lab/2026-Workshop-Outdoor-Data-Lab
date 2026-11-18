from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from commons.api.geo import SpatialFilterSet

from .models import LArea, LiMunicipality, LLinear, LPoint

# Spatial filters run on the native, GiST-indexed Lambert-93 "geom" column:
# the WGS84 input is reprojected once in SQL.


class LAreaFilter(SpatialFilterSet):
    type_code = filters.CharFilter(field_name="type__type_code")
    area_code = filters.CharFilter(field_name="area_code")
    name = filters.CharFilter(field_name="area_name", lookup_expr="icontains")

    class Meta:
        model = LArea
        fields = ["enable"]


class LLinearFilter(SpatialFilterSet):
    type_code = filters.CharFilter(field_name="type__type_code")
    name = filters.CharFilter(field_name="linear_name", lookup_expr="icontains")

    class Meta:
        model = LLinear
        fields = ["linear_code", "enable"]


class LPointFilter(SpatialFilterSet):
    type_code = filters.CharFilter(field_name="type__type_code")
    name = filters.CharFilter(field_name="point_name", lookup_expr="icontains")

    class Meta:
        model = LPoint
        fields = ["point_code", "enable"]


class LiMunicipalityFilter(filters.FilterSet):
    name = filters.CharFilter(field_name="nom_com", lookup_expr="icontains")

    class Meta:
        model = LiMunicipality
        fields = ["insee_com", "insee_dep", "insee_reg", "code_epci"]


class LAreaCountFilter(LAreaFilter):
    """Filter for LArea that returns areas intersecting with a given area code,
    excluding other areas with the same type_code."""

    area_code = filters.CharFilter(
        method="filter_by_area_code",
        label="Area code",
        help_text="Filter areas that intersect with the given area code (e.g., '05')"
    )

    type_code = filters.CharFilter(
        method="filter_by_type_code",
        label="Type code",
        help_text="Filter areas by type code (e.g., 'COM', 'DEP')"
    )

    def filter_by_area_code(self, queryset, name, value):
        """Filter areas that intersect with the specified area code.
        Includes the exact area found AND other areas that intersect,
        but excludes other areas with the same type_code."""
        try:
            parent_area = LArea.objects.get(area_code=value)
            return queryset.filter(
                Q(area_code=value) |
                (
                    Q(geom_4326__intersects=parent_area.geom_4326) &
                    ~Q(type__type_code=parent_area.type.type_code)
                )
            )
        except LArea.DoesNotExist:
            raise ValidationError(
                {"area_code": f"Area with code '{value}' does not exist."}
            )

    def filter_by_type_code(self, queryset, name, value):
        """Filter areas by type code."""
        return queryset.filter(type__type_code=value)

    class Meta:
        model = LArea
        fields = ["enable"]
