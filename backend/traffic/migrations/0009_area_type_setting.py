"""traffic.sync_counting_object_areas works on configurable grid types.

The ref_geo area types (``M1``, ``M0.5``…) are no longer hard-coded: they are
the ``area_types`` argument, else the comma-separated ``traffic.area_types``
session variable, else ``M1``. counting_object_areas holds the cells of every
listed grid (id_area is unique across types). The Django project sets the
variable on every new connection from ``settings.AREA_TYPES`` (see
``TrafficConfig``), so the triggers of traffic.counting_objects use the same
grids.

After changing the setting, rebuild the table:
``manage.py sync_counting_object_areas``.
"""

from django.db import migrations

CREATE = """
DROP FUNCTION IF EXISTS traffic.sync_counting_object_areas(bigint);

CREATE OR REPLACE FUNCTION traffic.sync_counting_object_areas(
    object_id bigint DEFAULT NULL, area_types text[] DEFAULT NULL
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    grid_type_ids integer[];
    inserted integer;
BEGIN
    IF to_regclass('ref_geo.l_areas') IS NULL
       OR to_regclass('ref_geo.bib_areas_types') IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT array_agg(id_type) INTO grid_type_ids FROM ref_geo.bib_areas_types
    WHERE type_code = ANY(COALESCE(
        area_types,
        string_to_array(NULLIF(current_setting('traffic.area_types', true), ''), ','),
        ARRAY['M1']
    ));

    -- One query per case, not "object_id IS NULL OR ...": each uses its index (0007).
    IF object_id IS NULL THEN
        DELETE FROM traffic.counting_object_areas;
        INSERT INTO traffic.counting_object_areas (counting_object_id, id_area)
        SELECT co.id, cell.id_area
        FROM traffic.counting_objects co
        CROSS JOIN LATERAL (
            SELECT la.id_area
            FROM ref_geo.l_areas la
            WHERE la.id_type = ANY(grid_type_ids) AND ST_Intersects(la.geom_4326, co.geom)
        ) cell;
    ELSE
        DELETE FROM traffic.counting_object_areas coa WHERE coa.counting_object_id = object_id;
        INSERT INTO traffic.counting_object_areas (counting_object_id, id_area)
        SELECT co.id, cell.id_area
        FROM traffic.counting_objects co
        CROSS JOIN LATERAL (
            SELECT la.id_area
            FROM ref_geo.l_areas la
            WHERE la.id_type = ANY(grid_type_ids) AND ST_Intersects(la.geom_4326, co.geom)
        ) cell
        WHERE co.id = object_id;
    END IF;

    GET DIAGNOSTICS inserted = ROW_COUNT;
    RETURN inserted;
END
$$;
"""

# The function of migration 0007 (M1 hard-coded, one query per case).
RESTORE = """
DROP FUNCTION IF EXISTS traffic.sync_counting_object_areas(bigint, text[]);

CREATE OR REPLACE FUNCTION traffic.sync_counting_object_areas(object_id bigint DEFAULT NULL)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    m1 integer;
    inserted integer;
BEGIN
    IF to_regclass('ref_geo.l_areas') IS NULL
       OR to_regclass('ref_geo.bib_areas_types') IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT id_type INTO m1 FROM ref_geo.bib_areas_types WHERE type_code = 'M1';

    IF object_id IS NULL THEN
        DELETE FROM traffic.counting_object_areas;
        INSERT INTO traffic.counting_object_areas (counting_object_id, id_area)
        SELECT co.id, cell.id_area
        FROM traffic.counting_objects co
        CROSS JOIN LATERAL (
            SELECT la.id_area
            FROM ref_geo.l_areas la
            WHERE la.id_type = m1 AND ST_Intersects(la.geom_4326, co.geom)
        ) cell;
    ELSE
        DELETE FROM traffic.counting_object_areas coa WHERE coa.counting_object_id = object_id;
        INSERT INTO traffic.counting_object_areas (counting_object_id, id_area)
        SELECT co.id, cell.id_area
        FROM traffic.counting_objects co
        CROSS JOIN LATERAL (
            SELECT la.id_area
            FROM ref_geo.l_areas la
            WHERE la.id_type = m1 AND ST_Intersects(la.geom_4326, co.geom)
        ) cell
        WHERE co.id = object_id;
    END IF;

    GET DIAGNOSTICS inserted = ROW_COUNT;
    RETURN inserted;
END
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0008_ref_geo_m500_grid"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE, reverse_sql=RESTORE),
    ]
