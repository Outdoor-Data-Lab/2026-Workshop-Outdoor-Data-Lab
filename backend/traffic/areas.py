"""Synchronisation of traffic.counting_object_areas (see migration 0003)."""

from django.conf import settings
from django.db import connections


def sync_counting_object_areas(using="default", object_id=None, area_types=None):
    """Recompute the cells of one counting object, or of all of them.

    The grids are ``area_types`` (ref_geo type_codes), by default ``settings.AREA_TYPES``.
    Return the number of rows inserted, or None if ref_geo is not loaded.
    """
    area_types = list(area_types or settings.AREA_TYPES)
    with connections[using].cursor() as cursor:
        cursor.execute(
            "SELECT traffic.sync_counting_object_areas(%s, %s)", [object_id, area_types]
        )
        return cursor.fetchone()[0]

