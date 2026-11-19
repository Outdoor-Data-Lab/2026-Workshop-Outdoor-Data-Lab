from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import viewsets
from rest_framework_gis.filters import InBBoxFilter
from django_filters.rest_framework import filters

from ref_geo.filters import LAreaAreaFilter
from commons.api.geo import GeoJsonLimitOffsetPagination

from . import serializers
from .querysets import GRID, TAXA_GRID, cells_with_status_taxa

class LAreaAreaTaxonStatusFilter(LAreaAreaFilter):
    has_protected_or_threatened_taxa = filters.BooleanFilter(
        method="filter_by_protected_or_threatened_taxa",
        label="Has protected or threatened taxa",
        help_text="Only show areas that have protected or threatened taxa (count > 0)"
    )
    def filter_by_protected_or_threatened_taxa(self, queryset, name, value):
        """Filter areas that have protected or threatened taxa (count > 0)."""
        if value:
            # Not on the count annotation: it would be computed for every cell of the grid.
            return queryset.filter(id_area__in=cells_with_status_taxa())
        return queryset


class TaxonAreaViewSet(viewsets.ReadOnlyModelViewSet):
    """Base read-only geographic view filtered with a WGS84 ``in_bbox``."""

    pagination_class = GeoJsonLimitOffsetPagination
    filter_backends = [
        InBBoxFilter,
        DjangoFilterBackend,
        drf_filters.OrderingFilter,
    ]
    filterset_class = LAreaAreaTaxonStatusFilter
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
