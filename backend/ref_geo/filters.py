from django.contrib.gis.gdal import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Point, Polygon
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from .models import LArea, LiMunicipality, LLinear, LPoint


def parse_geometry(value):
    """GeoJSON geometry or WKT/EWKT -> GEOS geometry (WGS84 unless an SRID is given)."""
    geom = GEOSGeometry(value)
    if not geom.srid:
        geom.srid = 4326
    return geom


class BBoxMixin(filters.FilterSet):
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
    bbox_field = "geom_4326"

    def filter_bbox(self, queryset, name, value):
        try:
            xmin, ymin, xmax, ymax = (float(v) for v in value.split(","))
        except ValueError:
            raise ValidationError({"bbox": "Expected minlon,minlat,maxlon,maxlat."})
        box = Polygon.from_bbox((xmin, ymin, xmax, ymax))
        box.srid = 4326
        return queryset.filter(**{f"{self.bbox_field}__intersects": box})

    def filter_point(self, queryset, name, value):
        try:
            lon, lat = (float(v) for v in value.split(","))
        except ValueError:
            raise ValidationError({"point": "Expected lon,lat."})
        return queryset.filter(
            **{f"{self.bbox_field}__intersects": Point(lon, lat, srid=4326)}
        )

    def filter_geometry(self, queryset, name, value):
        try:
            geom = parse_geometry(value)
        except (ValueError, GDALException, GEOSException):
            raise ValidationError({name: "Invalid GeoJSON or WKT geometry."})
        return queryset.filter(**{f"{self.bbox_field}__{name}": geom})


class LAreaFilter(BBoxMixin):
    type_code = filters.CharFilter(field_name="type__type_code")
    area_code = filters.CharFilter(field_name="area_code")
    name = filters.CharFilter(field_name="area_name", lookup_expr="icontains")

    class Meta:
        model = LArea
        fields = ["enable"]


class LLinearFilter(BBoxMixin):
    bbox_field = "geom"
    type_code = filters.CharFilter(field_name="type__type_code")
    name = filters.CharFilter(field_name="linear_name", lookup_expr="icontains")

    class Meta:
        model = LLinear
        fields = ["linear_code", "enable"]


class LPointFilter(LLinearFilter):
    type_code = filters.CharFilter(field_name="type__type_code")
    name = filters.CharFilter(field_name="point_name", lookup_expr="icontains")

    class Meta:
        model = LPoint
        fields = ["point_code", "enable"]


class LiMunicipalityFilter(filters.FilterSet):
    name = filters.CharFilter(field_name="nom_com", lookup_expr="icontains")

    class Meta:
        model = LiMunicipality
        fields = ["insee_com", "insee_dep", "insee_reg", "code_epci"]
