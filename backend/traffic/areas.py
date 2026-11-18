"""Synchronisation of traffic.counting_object_areas (see migration 0003)."""

from django.db import connections


def sync_counting_object_areas(using="default", object_id=None):
    """Recompute the cells of one counting object, or of all of them.

    Return the number of rows inserted, or None if ref_geo is not loaded.
    """
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT traffic.sync_counting_object_areas(%s)", [object_id])
        return cursor.fetchone()[0]

