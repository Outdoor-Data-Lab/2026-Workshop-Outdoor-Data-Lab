from django.apps import AppConfig
from django.conf import settings
from django.db.backends.signals import connection_created


def set_area_types(sender, connection, **kwargs):
    """Tell the DB triggers which ref_geo grids to use (migration 0006)."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('traffic.area_types', %s, false)",
                [",".join(settings.AREA_TYPES)],
            )


def map_layers():
    """Traffic layers of the map (catalog.ts): one per counting object type, then the cells."""
    from .models import CountingObjectType

    types = CountingObjectType.objects.order_by("id")
    return [(f"traffic/{t.code}", "traffic", t.label) for t in types] + [
        ("traffic/area", "grid", "Fréquentation par maille")
    ]


class TrafficConfig(AppConfig):
    name = "traffic"

    def ready(self):
        connection_created.connect(set_area_types, dispatch_uid="traffic_set_area_types")

        from commons.models import register_layers, register_parsers

        from .parsers import PARSERS

        register_parsers(PARSERS)
        register_layers(map_layers)

        from . import signals  # noqa: F401 (connects the receivers)
