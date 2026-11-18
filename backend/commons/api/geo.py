"""API conventions shared by every app (commons, traffic, ref_geo...).

- relations exposed and filtered by code (``<relation>_code``); commons and
  traffic name their fields id, code, label, ref_geo keeps the GeoNature names
- read-only viewsets, filtered with django-filter, sorted with ``?ordering=``
- limit/offset pagination (``REST_FRAMEWORK`` settings)
- plain JSON by default, GeoJSON FeatureCollection with ``?format=geojson``
- spatial filters in WGS84: ``bbox``, ``point``, ``intersects``/``within``/``contains``
"""

from math import isfinite

from django.contrib.gis.gdal import GDALException, SRSException
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Point, Polygon
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings


def code_field(relation):
    """A relation exposed by its code: ``type_code = code_field("type")`` (null if empty)."""
    return serializers.SlugRelatedField(source=relation, slug_field="code", read_only=True)


class GeoJSONRenderer(JSONRenderer):
    """Selected with ``?format=geojson``; the serializers already build GeoJSON."""

    media_type = "application/geo+json"
    format = "geojson"


class FormatFirstNegotiation(DefaultContentNegotiation):
    """``?format=`` wins over the Accept header (stock DRF answers 406 otherwise)."""

    def select_renderer(self, request, renderers, format_suffix=None):
        fmt = format_suffix or request.query_params.get(api_settings.URL_FORMAT_OVERRIDE)
        if fmt:
            for renderer in renderers:
                if renderer.format == fmt:
                    return renderer, renderer.media_type
        return super().select_renderer(request, renderers, format_suffix)


class GeoJsonLimitOffsetPagination(LimitOffsetPagination):
    """Limit/offset pagination returning a FeatureCollection."""

    def get_paginated_response(self, data):
        return Response(
            {
                "type": "FeatureCollection",
                "count": self.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "features": data["features"],
            }
        )


def parse_geometry(value):
    """GeoJSON geometry or WKT/EWKT -> GEOS geometry (WGS84 unless an SRID is given)."""
    geom = GEOSGeometry(value)
    if not geom.srid:
        geom.srid = 4326
    elif geom.srid != 4326:
        geom.transform(4326)  # fails early on an unknown SRID
    return geom


class SpatialFilterSet(filters.FilterSet):
    """Spatial filters, all inputs in WGS84 (lon/lat).

    - ``bbox=minlon,minlat,maxlon,maxlat``
    - ``point=lon,lat``: features containing this point
    - ``intersects`` / ``within`` / ``contains``: a GeoJSON geometry or WKT
    """

    bbox = filters.CharFilter(method="filter_bbox")
    point = filters.CharFilter(method="filter_point")
    intersects = filters.CharFilter(method="filter_geometry")
    within = filters.CharFilter(method="filter_geometry")
    contains = filters.CharFilter(method="filter_geometry")
    # Geometry column to filter on; Django reprojects the WGS84 input if needed.
    spatial_field = "geom"

    def filter_bbox(self, queryset, name, value):
        try:
            xmin, ymin, xmax, ymax = (float(v) for v in value.split(","))
            if not all(map(isfinite, (xmin, ymin, xmax, ymax))):
                raise ValueError
        except ValueError:
            raise ValidationError({"bbox": "Expected minlon,minlat,maxlon,maxlat."})
        box = Polygon.from_bbox((xmin, ymin, xmax, ymax))
        box.srid = 4326
        return queryset.filter(**{f"{self.spatial_field}__intersects": box})

    def filter_point(self, queryset, name, value):
        try:
            lon, lat = (float(v) for v in value.split(","))
            if not (isfinite(lon) and isfinite(lat)):
                raise ValueError
        except ValueError:
            raise ValidationError({"point": "Expected lon,lat."})
        return queryset.filter(
            **{f"{self.spatial_field}__intersects": Point(lon, lat, srid=4326)}
        )

    def filter_geometry(self, queryset, name, value):
        try:
            geom = parse_geometry(value)
        except (ValueError, TypeError, GDALException, SRSException, GEOSException):
            raise ValidationError({name: "Invalid GeoJSON or WKT geometry."})
        return queryset.filter(**{f"{self.spatial_field}__{name}": geom})


class ReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    # Whitelist: DRF would otherwise allow ordering on any serializer field
    # (e.g. a geometry column, which is expensive to sort on).
    ordering_fields = ()


class GeoViewSet(ReadOnlyViewSet):
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
