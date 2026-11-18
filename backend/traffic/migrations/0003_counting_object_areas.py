"""Correspondence table between the counting objects and the 1 km grid cells.

traffic.counting_object_areas holds the M1 cells (ref_geo) each counting object
intersects. The object -> cell spatial join only changes when an object is
created or moved, so it is stored here; the measures are aggregated on the fly
through this table (see workshop2026/processing/score.py).

traffic.sync_counting_object_areas(object_id) (re)computes the cells of one
object, or of every object when called without argument. It is called:
- by triggers on traffic.counting_objects (insert, update of geom), per row;
- at the end of this migration, to fill the table;
- by ``manage.py sync_counting_object_areas`` (e.g. after loading ref_geo).

ref_geo is not managed by Django (loaded from the RefGeo dump): while
ref_geo.l_areas is missing, the function does nothing and returns NULL.
"""

import django.db.models.deletion
from django.db import migrations, models

CREATE_FUNCTIONS = """
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

CREATE OR REPLACE FUNCTION traffic.counting_objects_sync_areas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM traffic.sync_counting_object_areas(NEW.id);
    RETURN NULL;
END
$$;

CREATE TRIGGER counting_objects_insert_sync_areas
    AFTER INSERT ON traffic.counting_objects
    FOR EACH ROW EXECUTE FUNCTION traffic.counting_objects_sync_areas();

-- Django's save() rewrites every column: only recompute when geom changed.
CREATE TRIGGER counting_objects_update_sync_areas
    AFTER UPDATE OF geom ON traffic.counting_objects
    FOR EACH ROW
    WHEN (OLD.geom IS DISTINCT FROM NEW.geom)
    EXECUTE FUNCTION traffic.counting_objects_sync_areas();

SELECT traffic.sync_counting_object_areas();
"""

DROP_FUNCTIONS = """
DROP TRIGGER IF EXISTS counting_objects_update_sync_areas ON traffic.counting_objects;
DROP TRIGGER IF EXISTS counting_objects_insert_sync_areas ON traffic.counting_objects;
DROP FUNCTION IF EXISTS traffic.counting_objects_sync_areas();
DROP FUNCTION IF EXISTS traffic.sync_counting_object_areas(bigint);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0002_initial_reference_values"),
    ]

    operations = [
        migrations.CreateModel(
            name="CountingObjectArea",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "counting_object", "area",
                        blank=True, editable=False, primary_key=True, serialize=False,
                    ),
                ),
                (
                    "counting_object",
                    models.ForeignKey(
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="areas",
                        to="traffic.countingobject",
                    ),
                ),
                (
                    "area",
                    models.ForeignKey(
                        db_column="id_area",
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="counting_object_areas",
                        to="ref_geo.larea",
                    ),
                ),
            ],
            options={
                "db_table": 'traffic"."counting_object_areas',
            },
        ),
        migrations.RunSQL(sql=CREATE_FUNCTIONS, reverse_sql=DROP_FUNCTIONS),
    ]
