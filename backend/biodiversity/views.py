from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import viewsets
from rest_framework_gis.filters import InBBoxFilter

from ref_geo.filters import LAreaFilter, LAreaCountFilter
from commons.api.geo import GeoJsonLimitOffsetPagination

from . import serializers
from .querysets import GRID, TAXA_GRID


class TaxonAreaViewSet(viewsets.ReadOnlyModelViewSet):
    """Base read-only geographic view filtered with a WGS84 ``in_bbox``."""

    pagination_class = GeoJsonLimitOffsetPagination
    filter_backends = [
        InBBoxFilter,
        DjangoFilterBackend,
        drf_filters.OrderingFilter,
    ]
    filterset_class = LAreaCountFilter
    ordering_fields = ("id_area", "area_code", "area_name")
    bbox_filter_field = "geom_4326"
    bbox_filter_include_overlapping = True


class BiodivSyntheticDataAreaViewSet(TaxonAreaViewSet):
    """Protected and threatened taxon counts per configured grid area."""

    queryset = GRID.order_by("id_area")
    serializer_class = serializers.TaxonStatusAreaSerializer


class BiodivListTaxaAreaViewSet(TaxonAreaViewSet):
    """Protected or threatened taxa, nested within each grid area."""

    queryset = TAXA_GRID.order_by("id_area")
    serializer_class = serializers.TaxonListAreaSerializer
