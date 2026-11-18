from django.apps import AppConfig


class BiodiversityConfig(AppConfig):
    name = "biodiversity"

    def ready(self):
        from commons.models import register_parsers

        from .parsers import PARSERS

        register_parsers(PARSERS)
