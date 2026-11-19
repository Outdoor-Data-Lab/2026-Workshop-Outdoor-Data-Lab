from django.apps import AppConfig


class BiodiversityConfig(AppConfig):
    name = "biodiversity"

    def ready(self):
        from commons.models import register_layers, register_parsers

        from .parsers import PARSERS

        register_parsers(PARSERS)
        register_layers(lambda: [("biodiversity/area", "grid", "Taxons menacés par maille")])
