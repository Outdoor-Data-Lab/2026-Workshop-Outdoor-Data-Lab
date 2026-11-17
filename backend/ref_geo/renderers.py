from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import JSONRenderer
from rest_framework.settings import api_settings


class GeoJSONRenderer(JSONRenderer):
    """Selected with ``?format=geojson``; the serializers already build GeoJSON."""

    media_type = "application/geo+json"
    format = "geojson"


class FormatFirstNegotiation(DefaultContentNegotiation):
    """``?format=`` wins over the Accept header.

    Stock DRF also checks Accept against the renderer selected by ``?format=``,
    so ``?format=geojson`` with ``Accept: application/json`` gave a 406.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        fmt = format_suffix or request.query_params.get(
            api_settings.URL_FORMAT_OVERRIDE
        )
        if fmt:
            for renderer in renderers:
                if renderer.format == fmt:
                    return renderer, renderer.media_type
        return super().select_renderer(request, renderers, format_suffix)
