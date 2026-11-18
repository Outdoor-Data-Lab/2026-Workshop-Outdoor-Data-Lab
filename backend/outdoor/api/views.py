from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.settings import api_settings

from commons.api.geo import FormatFirstNegotiation, GeoJSONRenderer, GeoJsonLimitOffsetPagination
from ref_geo.filters import LAreaFilter
from ref_geo.models import LArea
from ref_geo.serializers import LAreaSerializer, LAreaGeoSerializer
from ref_geo.views import GeoViewSet
from ..models import Offer
from .serializers import OfferSerializer, OfferGeoSerializer, LAreaWithOffersCountSerializer, \
    LAreaGeoWithOffersCountSerializer, LAreaGeoWithOffersCountAndByPracticeSerializer, \
    LAreaWithOffersCountAndByPracticeSerializer
from .filters import OfferFilter


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing and retrieving outdoor offers.

    Supports both JSON and GeoJSON output formats via ?format=geojson
    Spatial filters: area (filter by l_area code)

    Example requests:
    - GET /api/offers/ -> JSON format
    - GET /api/offers/?format=geojson -> GeoJSON format
    - GET /api/offers/?area=26 -> Filter by area Drôme (JSON)
    - GET /api/offers/?area=26&format=geojson -> Filter by area code (GeoJSON)
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


# ... existing code ...

class LAreaCountViewSet(GeoViewSet):
    """API endpoint for listing areas with optional offers count.

    When type_code parameter is provided, areas are filtered by type and include offers count.
    When practice_count=true parameter is provided, also includes offers count by practice type.

    Example requests:
    - GET /api/areas/ -> List all areas
    - GET /api/areas/?type_code=COM -> List areas of type COM with offers count
    - GET /api/areas/?type_code=COM&practice_count=true -> With practice breakdown
    - GET /api/areas/?type_code=COM&format=geojson -> Same in GeoJSON format
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

        # Si type_code est fourni, filtrer par type
        type_code = self.request.query_params.get('type_code')
        if type_code:
            qs = qs.filter(type__type_code=type_code)

        if not self.is_geojson():
            qs = qs.defer("geom_4326")
        return qs

    def get_serializer_class(self):
        """Retourner le serializer approprié basé sur les paramètres de requête."""
        type_code = self.request.query_params.get('type_code')
        practice_count = self.request.query_params.get('practice_count', '').lower() == 'true'

        if type_code:
            if practice_count:
                # Avec comptage par practice
                if self.is_geojson():
                    return LAreaGeoWithOffersCountAndByPracticeSerializer
                return LAreaWithOffersCountAndByPracticeSerializer
            else:
                # Comptage global uniquement
                if self.is_geojson():
                    return LAreaGeoWithOffersCountSerializer
                return LAreaWithOffersCountSerializer
        return super().get_serializer_class()