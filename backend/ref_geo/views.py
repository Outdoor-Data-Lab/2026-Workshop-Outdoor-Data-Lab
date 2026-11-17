from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import viewsets
from rest_framework.settings import api_settings

from . import serializers
from .renderers import GeoJSONRenderer
from .pagination import GeoJsonLimitOffsetPagination
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


class RefGeoViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]


class BibAreasTypeViewSet(RefGeoViewSet):
    queryset = BibAreasType.objects.order_by("id_type")
    serializer_class = serializers.BibAreasTypeSerializer
    filterset_fields = ["type_code", "ref_name"]


class BibLinearsTypeViewSet(RefGeoViewSet):
    queryset = BibLinearsType.objects.order_by("id_type")
    serializer_class = serializers.BibLinearsTypeSerializer
    filterset_fields = ["type_code"]


class BibPointsTypeViewSet(RefGeoViewSet):
    queryset = BibPointsType.objects.order_by("id_type")
    serializer_class = serializers.BibPointsTypeSerializer
    filterset_fields = ["type_code"]


class GeoViewSet(RefGeoViewSet):
    """Plain JSON by default, GeoJSON FeatureCollection with ``?format=geojson``."""

    renderer_classes = [*api_settings.DEFAULT_RENDERER_CLASSES, GeoJSONRenderer]
    geo_serializer_class = None

    def is_geojson(self):
        return getattr(self.request.accepted_renderer, "format", None) == "geojson"

    def get_serializer_class(self):
        return self.geo_serializer_class if self.is_geojson() else super().get_serializer_class()

    @property
    def paginator(self):
        if self.is_geojson():
            if not hasattr(self, "_geo_paginator"):
                self._geo_paginator = GeoJsonLimitOffsetPagination()
            return self._geo_paginator
        return super().paginator


class LAreaViewSet(GeoViewSet):
    """Areas (communes, grids, zonings...).

    Filters: ``type_code``, ``area_code``, ``name``, ``enable``,
    ``bbox=minlon,minlat,maxlon,maxlat``. Add ``format=geojson`` for a
    GeoJSON FeatureCollection (WGS84 geometry).
    """

    # defer heavy geometry columns: the serializer only reads geom_4326 on demand
    queryset = (
        LArea.objects.select_related("type")
        .defer("geom", "centroid")
        .order_by("id_area")
    )
    serializer_class = serializers.LAreaSerializer
    geo_serializer_class = serializers.LAreaGeoSerializer
    filterset_class = LAreaFilter

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


class LPointViewSet(GeoViewSet):
    queryset = LPoint.objects.select_related("type").order_by("id_point")
    serializer_class = serializers.LPointSerializer
    geo_serializer_class = serializers.LPointGeoSerializer
    filterset_class = LPointFilter


class LiMunicipalityViewSet(RefGeoViewSet):
    queryset = LiMunicipality.objects.order_by("insee_com")
    serializer_class = serializers.LiMunicipalitySerializer
    filterset_class = LiMunicipalityFilter


class LiGridViewSet(RefGeoViewSet):
    queryset = LiGrid.objects.order_by("id_grid")
    serializer_class = serializers.LiGridSerializer
    filterset_fields = ["area"]


class TLinearGroupViewSet(RefGeoViewSet):
    queryset = TLinearGroup.objects.order_by("id_group")
    serializer_class = serializers.TLinearGroupSerializer
    filterset_fields = ["code"]
