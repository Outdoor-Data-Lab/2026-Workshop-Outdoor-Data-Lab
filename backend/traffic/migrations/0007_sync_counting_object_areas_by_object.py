"""traffic.sync_counting_object_areas (migration 0003): one query per case.

The condition "object_id IS NULL OR id = object_id" let Postgres use a generic
plan that scans counting_objects and counting_object_areas in full: called by
the insert trigger for each new object, it made an import ever slower as the
tables grew (2 to 24 s per 1,000 Outdoorvision tracks). With one query for one
object and one for all, each uses its index: 0.7 s per 1,000 tracks.
Same results; the triggers and the command are unchanged.
"""

from django.db import migrations

FUNCTION = """
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

    -- From each object to its cells: uses the GiST index of l_areas.geom_4326
    -- instead of scanning the ~600,000 cells.
    -- One query per case, not "object_id IS NULL OR ...": each then uses its index.
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

# The function of migration 0003.
PREVIOUS_FUNCTION = """
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

    DELETE FROM traffic.counting_object_areas coa
    WHERE object_id IS NULL OR coa.counting_object_id = object_id;

    -- From each object to its cells: uses the GiST index of l_areas.geom_4326
    -- instead of scanning the ~600,000 cells.
    INSERT INTO traffic.counting_object_areas (counting_object_id, id_area)
    SELECT co.id, cell.id_area
    FROM traffic.counting_objects co
    CROSS JOIN LATERAL (
        SELECT la.id_area
        FROM ref_geo.l_areas la
        WHERE la.id_type = m1 AND ST_Intersects(la.geom_4326, co.geom)
    ) cell
    WHERE object_id IS NULL OR co.id = object_id;

    GET DIAGNOSTICS inserted = ROW_COUNT;
    RETURN inserted;
END
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("traffic", "0006_counting_measure_unique_key"),
    ]

    operations = [
        migrations.RunSQL(FUNCTION, reverse_sql=PREVIOUS_FUNCTION),
    ]
