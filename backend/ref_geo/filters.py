from django_filters import rest_framework as filters

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
