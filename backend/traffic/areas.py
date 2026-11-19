"""Synchronisation of traffic.counting_object_areas (see migration 0003)."""

from django.conf import settings
from django.db import connections, transaction


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


def refresh_cell_day_counts(using="default"):
    """Rebuild traffic.cell_day_counts (see CellDayCount); return its number of rows."""
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT traffic.refresh_cell_day_counts()")
        return cursor.fetchone()[0]


LINES = "GeometryType(co.geom) IN ('LINESTRING', 'MULTILINESTRING')"


def fill_link_lengths(using="default", shard=(0, 1), batch_size=500, progress=None):
    """Compute ``length_m`` of the links of line objects that have none yet.

    Same formula as ``traffic.sync_counting_object_areas``, without rebuilding the
    links: by batches of objects, one transaction each, so it can be stopped and
    resumed. ``shard=(i, n)`` handles the objects with ``id % n == i``: run
    several processes with the same ``n`` to use several cores. ``progress`` is
    called with the number of links updated so far. Return that number.
    """
    index, count = shard
    done = 0
    with connections[using].cursor() as cursor:
        cursor.execute(
            f"""SELECT DISTINCT coa.counting_object_id
                FROM traffic.counting_object_areas coa
                JOIN traffic.counting_objects co ON co.id = coa.counting_object_id
                WHERE coa.length_m IS NULL AND {LINES} AND co.id %% %s = %s
                ORDER BY 1""",
            [count, index],
        )
        object_ids = [row[0] for row in cursor.fetchall()]
    for start in range(0, len(object_ids), batch_size):
        with transaction.atomic(using=using), connections[using].cursor() as cursor:
            cursor.execute(
                f"""UPDATE traffic.counting_object_areas coa
                    SET length_m = ST_Length(ST_CollectionExtract(
                        ST_Intersection(co.geom, la.geom_4326), 2)::geography)
                    FROM traffic.counting_objects co, ref_geo.l_areas la
                    WHERE co.id = coa.counting_object_id AND la.id_area = coa.id_area
                      AND coa.length_m IS NULL AND {LINES}
                      AND co.id = ANY(%s)""",
                [object_ids[start : start + batch_size]],
            )
            done += cursor.rowcount
        if progress:
            progress(done)
    return done
