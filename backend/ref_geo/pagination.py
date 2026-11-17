from collections import OrderedDict

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class GeoJsonLimitOffsetPagination(LimitOffsetPagination):
    """Limit/offset pagination returning a FeatureCollection (as rest_framework_gis'
    GeoJsonPagination does for page numbers)."""

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("type", "FeatureCollection"),
                    ("count", self.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("features", data["features"]),
                ]
            )
        )
