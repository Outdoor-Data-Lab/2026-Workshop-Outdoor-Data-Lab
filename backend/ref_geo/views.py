from django.contrib.gis.db.models.functions import Transform

from commons.api.geo import GeoViewSet, ReadOnlyViewSet

from . import serializers
from .filters import (
    LAreaFilter,
    LiMunicipalityFilter,
    LLinearFilter,
    LPointFilter,
)
from .models import (
    BibAreasType,
    BibLinearsType,
    BibPointsType,
    LArea,
    LiGrid,
    LiMunicipality,
    LLinear,
    LPoint,
    TLinearGroup,
)

TYPE_ORDERING = ("id_type", "type_code", "type_name")


class BibAreasTypeViewSet(ReadOnlyViewSet):
    queryset = BibAreasType.objects.order_by("id_type")
    serializer_class = serializers.BibAreasTypeSerializer
    filterset_fields = ["type_code", "ref_name"]
    ordering_fields = TYPE_ORDERING


class BibLinearsTypeViewSet(ReadOnlyViewSet):
    queryset = BibLinearsType.objects.order_by("id_type")
    serializer_class = serializers.BibLinearsTypeSerializer
    filterset_fields = ["type_code"]
    ordering_fields = TYPE_ORDERING


class BibPointsTypeViewSet(ReadOnlyViewSet):
    queryset = BibPointsType.objects.order_by("id_type")
    serializer_class = serializers.BibPointsTypeSerializer
    filterset_fields = ["type_code"]
    ordering_fields = TYPE_ORDERING


def wgs84_queryset(queryset, with_geometry):
    """Never load the Lambert-93 column; reproject in SQL when geometry is needed."""
    queryset = queryset.defer("geom", "geojson_4326")
    if with_geometry:
        queryset = queryset.annotate(geom_4326=Transform("geom", 4326))
    return queryset


class LAreaViewSet(GeoViewSet):
    """Areas (communes, grids, zonings...)."""

    # defer heavy geometry columns: the serializer only reads geom_4326 on demand
    queryset = (
        LArea.objects.select_related("type")
        .defer("geom", "centroid")
        .order_by("id_area")
    )
    serializer_class = serializers.LAreaSerializer
    geo_serializer_class = serializers.LAreaGeoSerializer
    filterset_class = LAreaFilter
    ordering_fields = ("id_area", "area_name", "area_code")

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.is_geojson():
            qs = qs.defer("geom_4326")
        return qs


class LLinearViewSet(GeoViewSet):
    queryset = LLinear.objects.select_related("type").order_by("id_linear")
    serializer_class = serializers.LLinearSerializer
    geo_serializer_class = serializers.LLinearGeoSerializer
    filterset_class = LLinearFilter
    ordering_fields = ("id_linear", "linear_name", "linear_code")

    def get_queryset(self):
        return wgs84_queryset(super().get_queryset(), self.is_geojson())


class LPointViewSet(GeoViewSet):
    queryset = LPoint.objects.select_related("type").order_by("id_point")
    serializer_class = serializers.LPointSerializer
    geo_serializer_class = serializers.LPointGeoSerializer
    filterset_class = LPointFilter
    ordering_fields = ("id_point", "point_name", "point_code")

    def get_queryset(self):
        return wgs84_queryset(super().get_queryset(), self.is_geojson())


class LiMunicipalityViewSet(ReadOnlyViewSet):
    queryset = LiMunicipality.objects.order_by("insee_com")
    serializer_class = serializers.LiMunicipalitySerializer
    filterset_class = LiMunicipalityFilter
    ordering_fields = ("insee_com", "nom_com", "population")


class LiGridViewSet(ReadOnlyViewSet):
    queryset = LiGrid.objects.order_by("id_grid")
    serializer_class = serializers.LiGridSerializer
    filterset_fields = ["area"]
    ordering_fields = ("id_grid",)


class TLinearGroupViewSet(ReadOnlyViewSet):
    queryset = TLinearGroup.objects.order_by("id_group")
    serializer_class = serializers.TLinearGroupSerializer
    filterset_fields = ["code"]
    ordering_fields = ("id_group", "code", "name")
