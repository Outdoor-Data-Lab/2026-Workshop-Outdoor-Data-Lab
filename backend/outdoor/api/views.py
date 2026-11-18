from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.settings import api_settings

from ref_geo.filters import LAreaFilter
from ref_geo.models import LArea
from ref_geo.serializers import LAreaSerializer, LAreaGeoSerializer
from ref_geo.views import GeoViewSet
from ..models import Offer
from .serializers import OfferSerializer, OfferGeoSerializer
from .filters import OfferFilter
from ref_geo.renderers import FormatFirstNegotiation, GeoJSONRenderer
from ref_geo.pagination import GeoJsonLimitOffsetPagination


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing and retrieving outdoor offers.

    Supports both JSON and GeoJSON output formats via ?format=geojson
    Spatial filters: area (filter by l_area id)

    Example requests:
    - GET /api/offers/ -> JSON format
    - GET /api/offers/?format=geojson -> GeoJSON format
    - GET /api/offers/?area=123 -> Filter by area id (JSON)
    - GET /api/offers/?area=123&format=geojson -> Filter by area id (GeoJSON)
    """

    queryset = Offer.objects.select_related('practice', 'source')
    serializer_class = OfferSerializer
    geo_serializer_class = OfferGeoSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = OfferFilter
    ordering_fields = ['date_create', 'date_update', 'external_id']
    ordering = ['-date_create']

    # GeoJSON support
    renderer_classes = [*api_settings.DEFAULT_RENDERER_CLASSES, GeoJSONRenderer]
    content_negotiation_class = FormatFirstNegotiation

    def is_geojson(self):
        """Check if the request asks for GeoJSON format."""
        request = getattr(self, "request", None)
        return getattr(getattr(request, "accepted_renderer", None), "format", None) == "geojson"

    def get_serializer_class(self):
        """Return GeoJSON serializer if format=geojson, otherwise return JSON serializer."""
        return self.geo_serializer_class if self.is_geojson() else self.serializer_class

    @property
    def paginator(self):
        """Use GeoJSON pagination when format=geojson."""
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
    queryset = (
        LArea.objects.select_related("type")
        .defer("geom", "centroid")
        .order_by("id_area")
    )
    serializer_class = LAreaSerializer
    geo_serializer_class = LAreaGeoSerializer
    filterset_class = LAreaFilter
    ordering_fields = ("id_area", "area_name", "area_code")

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.is_geojson():
            qs = qs.defer("geom_4326")
        return qs

    @action(detail=False, methods=['get'])
    def by_type_with_offers(self, request):
        """Get all areas by type_code with offers count in each area.

        Query parameters:
            - type_code: Filter by area type code (required)

        Example: GET /api/areas/by_type_with_offers/?type_code=COM
        """
        type_code = request.query_params.get('type_code')

        if not type_code:
            return Response(
                {"error": "type_code parameter is required"},
                status=400
            )

        # Get areas of the specified type
        areas = (
            LArea.objects
            .select_related("type")
            .filter(type__type_code=type_code)
            .defer("geom", "centroid", "geom_4326")
            .order_by("id_area")
        )

        # Annotate with offers count
        areas_with_counts = []
        for area in areas:
            if area.geom_4326:
                offers_count = Offer.objects.filter(geom__intersects=area.geom_4326).count()
            else:
                offers_count = 0

            areas_with_counts.append({
                **LAreaSerializer(area).data,
                "offers_count": offers_count
            })

        return Response({
            "type_code": type_code,
            "count": len(areas_with_counts),
            "results": areas_with_counts
        })
