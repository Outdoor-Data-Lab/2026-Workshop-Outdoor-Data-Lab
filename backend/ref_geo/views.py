from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from django.contrib.gis.db.models.functions import Transform
from rest_framework import viewsets
from rest_framework.settings import api_settings

from . import serializers
from .renderers import FormatFirstNegotiation, GeoJSONRenderer
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
    # Whitelist: DRF would otherwise allow ordering on any serializer field
    # (e.g. a geometry column, which is expensive to sort on).
    ordering_fields = ()


class BibAreasTypeViewSet(RefGeoViewSet):
    queryset = BibAreasType.objects.order_by("id_type")
    serializer_class = serializers.BibAreasTypeSerializer
    filterset_fields = ["type_code", "ref_name"]
    ordering_fields = ("id_type", "type_code", "type_name")


class BibLinearsTypeViewSet(RefGeoViewSet):
    queryset = BibLinearsType.objects.order_by("id_type")
    serializer_class = serializers.BibLinearsTypeSerializer
    filterset_fields = ["type_code"]
    ordering_fields = ("id_type", "type_code", "type_name")


class BibPointsTypeViewSet(RefGeoViewSet):
    queryset = BibPointsType.objects.order_by("id_type")
    serializer_class = serializers.BibPointsTypeSerializer
    filterset_fields = ["type_code"]
    ordering_fields = ("id_type", "type_code", "type_name")


class GeoViewSet(RefGeoViewSet):
    """Plain JSON by default, GeoJSON FeatureCollection with ``?format=geojson``."""

    renderer_classes = [*api_settings.DEFAULT_RENDERER_CLASSES, GeoJSONRenderer]
    content_negotiation_class = FormatFirstNegotiation
    geo_serializer_class = None

    def is_geojson(self):
        # request / accepted_renderer do not exist during OpenAPI schema generation
        request = getattr(self, "request", None)
        return getattr(getattr(request, "accepted_renderer", None), "format", None) == "geojson"

    def get_serializer_class(self):
        return self.geo_serializer_class if self.is_geojson() else super().get_serializer_class()

    @property
    def paginator(self):
        if self.is_geojson():
            if not hasattr(self, "_geo_paginator"):
                self._geo_paginator = GeoJsonLimitOffsetPagination()
            return self._geo_paginator
        return super().paginator


def wgs84_queryset(queryset, with_geometry):
    """Never load the Lambert-93 column; reproject in SQL when geometry is needed."""
    queryset = queryset.defer("geom", "geojson_4326")
    if with_geometry:
        queryset = queryset.annotate(geom_4326=Transform("geom", 4326))
    return queryset


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


class LiMunicipalityViewSet(RefGeoViewSet):
    queryset = LiMunicipality.objects.order_by("insee_com")
    serializer_class = serializers.LiMunicipalitySerializer
    filterset_class = LiMunicipalityFilter
    ordering_fields = ("insee_com", "nom_com", "population")


class LiGridViewSet(RefGeoViewSet):
    queryset = LiGrid.objects.order_by("id_grid")
    serializer_class = serializers.LiGridSerializer
    filterset_fields = ["area"]
    ordering_fields = ("id_grid",)


class TLinearGroupViewSet(RefGeoViewSet):
    queryset = TLinearGroup.objects.order_by("id_group")
    serializer_class = serializers.TLinearGroupSerializer
    filterset_fields = ["code"]
    ordering_fields = ("id_group", "code", "name")
