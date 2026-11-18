from django.apps import AppConfig

# Format code -> parser class of the outdoor imports (registered in commons by
# OutdoorConfig.ready()). A path, not a class: the parser imports commons models.
PARSERS = {"offers": "outdoor.parsers.OfferParser"}


class OutdoorConfig(AppConfig):
    name = "outdoor"

    def ready(self):
        from commons.models import register_parsers

        register_parsers(PARSERS)
