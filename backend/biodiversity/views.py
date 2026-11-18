from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import viewsets
from rest_framework_gis.filters import InBBoxFilter

from ref_geo.filters import LAreaFilter
from ref_geo.pagination import GeoJsonLimitOffsetPagination
from rest_framework_gis.filters import InBBoxFilter
from . import serializers
from .querysets import GRID


class TaxonStatusAreaViewSet(viewsets.ReadOnlyModelViewSet):
    """Taxon status counts per 1 km area.

    Use ``bbox=minlon,minlat,maxlon,maxlat`` to restrict the returned areas.
    Coordinates are WGS84 longitudes and latitudes.
    """

    queryset = GRID.order_by("id_area")
    serializer_class = serializers.TaxonStatusAreaSerializer
    pagination_class = GeoJsonLimitOffsetPagination
    filter_backends = [InBBoxFilter, DjangoFilterBackend, drf_filters.OrderingFilter,]
    search_area = ['area_code', 'area_name', 'type__type_code']
    filterset_class = LAreaFilter
    ordering_fields = ("id_area", "area_code", "area_name")
    bbox_filter_include_overlapping = True
