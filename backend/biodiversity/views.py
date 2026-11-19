import hashlib

from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework_gis.filters import InBBoxFilter
from django_filters.rest_framework import filters

from ref_geo.filters import LAreaAreaFilter
from commons.api.geo import GeoJsonLimitOffsetPagination
from commons.models import data_version

from . import serializers
from .querysets import GRID, TAXA_GRID, cells_with_status_taxa

class LAreaAreaTaxonStatusFilter(LAreaAreaFilter):
    taxa_status = filters.ChoiceFilter(
        method="filter_by_taxa_status",
        label="Taxa conservation status",
        help_text="Filter by protected and/or threatened taxa",
        choices=[
            ('protected', 'Only protected'),
            ('threatened', 'Only threatened'),
            ('either', 'Protected or threatened'),
            ('both', 'Both protected and threatened'),
        ]
    )

    def filter_by_taxa_status(self, queryset, name, value):
        """Filter areas by protected and/or threatened taxa presence."""
        if not value:
            return queryset

        from .querysets import PROTECTION_STATUS, REDLIST_STATUS

        if value == 'protected':
            return queryset.filter(id_area__in=cells_with_status_taxa(PROTECTION_STATUS))
        elif value == 'threatened':
            return queryset.filter(id_area__in=cells_with_status_taxa(REDLIST_STATUS))
        elif value == 'either':
            # Protected or threatened (at least one)
            return queryset.filter(id_area__in=cells_with_status_taxa())
        elif value == 'both':
            # Both protected AND threatened
            protected_cells = set(cells_with_status_taxa(PROTECTION_STATUS))
            threatened_cells = set(cells_with_status_taxa(REDLIST_STATUS))
            both_cells = protected_cells & threatened_cells
            return queryset.filter(id_area__in=both_cells)

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

    def list(self, request, *args, **kwargs):
        """Cached until the next import, or a week (see ``cells_with_status_taxa``):
        the taxa of 1,000 cells take seconds on the 800,000 observations."""
        url = request.build_absolute_uri()
        key = f"biodiv-response:{data_version()}:{hashlib.sha1(url.encode()).hexdigest()}"
        data = cache.get(key)
        if data is None:
            data = super().list(request, *args, **kwargs).data
            cache.set(key, data, timeout=7 * 24 * 3600)
        return Response(data)


class BiodivSyntheticDataAreaViewSet(TaxonAreaViewSet):
    """Protected and threatened taxon counts per configured grid area."""

    queryset = GRID.order_by("id_area")
    serializer_class = serializers.TaxonStatusAreaSerializer


class BiodivListTaxaAreaViewSet(TaxonAreaViewSet):
    """Protected or threatened taxa, nested within each grid area."""

    queryset = TAXA_GRID.order_by("id_area")
    serializer_class = serializers.TaxonListAreaSerializer
