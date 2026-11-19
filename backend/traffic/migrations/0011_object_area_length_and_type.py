"""counting_object_areas: intersected length and grid type of each (object, cell).

- ``length_m``: length in metres of the part of a line object inside the cell
  (NULL for points). The scores weight a measure by it, as the R analysis does
  (BTA_PrepareStrava: DistPers = count x length of the piece in the cell), so a
  short corner clip no longer weighs as much as a long traverse.
- ``id_type``: the ref_geo type of the cell, copied here so that selecting a
  grid no longer joins ref_geo.l_areas and bib_areas_types.
- index (id_type, id_area, counting_object_id): from a grid / cell to its objects.

The migration only adds the columns and fills ``id_type`` (seconds). The
lengths of the existing links need a geometry intersection per (object, cell),
about 10 minutes on 100,000 tracks: they are filled by ``manage.py
sync_counting_object_areas --lengths`` (in batches, resumable, shardable), not
here. Until then a line's ``length_m`` is NULL and counts as a point (1 km).
New and moved objects get their lengths from the sync function (the triggers).
"""

from importlib import import_module

import django.db.models.deletion
from django.db import migrations, models

FUNCTION = """
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

    -- length_m: metres of the line inside the cell (ST_CollectionExtract(.., 2)
    -- drops the points a boundary contact can add); NULL for points and polygons.
    -- One query per case, not "object_id IS NULL OR ...": each uses its index (0007).
    IF object_id IS NULL THEN
        DELETE FROM traffic.counting_object_areas;
        INSERT INTO traffic.counting_object_areas
            (counting_object_id, id_area, id_type, length_m)
        SELECT co.id, cell.id_area, cell.id_type,
               CASE WHEN GeometryType(co.geom) IN ('LINESTRING', 'MULTILINESTRING')
                    THEN ST_Length(ST_CollectionExtract(
                        ST_Intersection(co.geom, cell.geom_4326), 2)::geography)
               END
        FROM traffic.counting_objects co
        CROSS JOIN LATERAL (
            SELECT la.id_area, la.id_type, la.geom_4326
            FROM ref_geo.l_areas la
            WHERE la.id_type = ANY(grid_type_ids) AND ST_Intersects(la.geom_4326, co.geom)
        ) cell;
    ELSE
        DELETE FROM traffic.counting_object_areas coa WHERE coa.counting_object_id = object_id;
        INSERT INTO traffic.counting_object_areas
            (counting_object_id, id_area, id_type, length_m)
        SELECT co.id, cell.id_area, cell.id_type,
               CASE WHEN GeometryType(co.geom) IN ('LINESTRING', 'MULTILINESTRING')
                    THEN ST_Length(ST_CollectionExtract(
                        ST_Intersection(co.geom, cell.geom_4326), 2)::geography)
               END
        FROM traffic.counting_objects co
        CROSS JOIN LATERAL (
            SELECT la.id_area, la.id_type, la.geom_4326
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


FILL_TYPES = """
DO $$
BEGIN
    IF to_regclass('ref_geo.l_areas') IS NOT NULL THEN
        UPDATE traffic.counting_object_areas coa SET id_type = la.id_type
        FROM ref_geo.l_areas la WHERE la.id_area = coa.id_area;
    END IF;
END
$$;
"""


def previous_function():
    return import_module("traffic.migrations.0009_area_type_setting").CREATE


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0010_counting_object_geom_tiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="countingobjectarea",
            name="length_m",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="countingobjectarea",
            name="area_type",
            field=models.ForeignKey(
                blank=True,
                db_column="id_type",
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="ref_geo.bibareastype",
            ),
        ),
        migrations.AddIndex(
            model_name="countingobjectarea",
            index=models.Index(
                fields=["area_type", "area", "counting_object"],
                name="coa_type_area_object",
            ),
        ),
        migrations.RunSQL(sql=FUNCTION, reverse_sql=previous_function()),
        # Cheap: no geometry involved (does nothing while ref_geo is not loaded).
        migrations.RunSQL(sql=FILL_TYPES, reverse_sql=migrations.RunSQL.noop),
    ]
