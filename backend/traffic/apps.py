from django.apps import AppConfig


class TrafficConfig(AppConfig):
    name = "traffic"

    def ready(self):
        from commons.models import register_parsers

        from .parsers import PARSERS

        register_parsers(PARSERS)
