from rest_framework.renderers import JSONRenderer


class GeoJSONRenderer(JSONRenderer):
    """Selected with ``?format=geojson``; the serializers already build GeoJSON."""

    media_type = "application/geo+json"
    format = "geojson"
