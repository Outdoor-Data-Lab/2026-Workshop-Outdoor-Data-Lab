"""Add the 500 m grid (ref_geo type "M0.5") to ref_geo.

ref_geo is not managed by Django (``MIGRATION_MODULES["ref_geo"] = None``), so
this data migration lives in the "traffic" app, like the ref_geo triggers of
0003. Nothing is done while the ref_geo tables are missing (fresh test DB):
load the RefGeo dump first, then run this migration, or re-run it later.

The cells come from ``data/m500_cells.csv.gz`` (area_code, WGS84 polygon).
Native geometry (2154), centroid and geom_4326 are derived in SQL. The type id
is looked up, never hard-coded; the migration is idempotent.
"""

import csv
import gzip
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).parent / "data" / "m500_cells.csv.gz"
TYPE_CODE = "M0.5"
BATCH = 5000

INSERT_TYPE = """
INSERT INTO ref_geo.bib_areas_types (type_name, type_code, type_desc)
SELECT 'Mailles0.5*0.5', %s,
       'Mailles (non officielles de 500m basées sur le référentiel RGF93 - 2154)'
WHERE NOT EXISTS (SELECT 1 FROM ref_geo.bib_areas_types WHERE type_code = %s)
"""

INSERT_AREAS = """
INSERT INTO ref_geo.l_areas
    (id_type, area_code, area_name, geom, centroid, geom_4326, source, comment,
     enable, meta_create_date, meta_update_date)
SELECT t.id_type, c.code, 'Maille 500 m - ' || c.code,
       ST_Multi(ST_Transform(g.geom_4326, 2154)),
       ST_Centroid(ST_Transform(g.geom_4326, 2154)),
       ST_Multi(g.geom_4326),
       'généré', 'Grille 500 m', true, now(), now()
FROM unnest(%s::text[], %s::text[]) AS c(code, wkt)
CROSS JOIN LATERAL (SELECT ST_GeomFromText(c.wkt, 4326) AS geom_4326) g
CROSS JOIN (SELECT id_type FROM ref_geo.bib_areas_types WHERE type_code = %s) t
WHERE NOT EXISTS (
    SELECT 1 FROM ref_geo.l_areas la
    WHERE la.id_type = t.id_type AND la.area_code = c.code
)
"""

DELETE_AREAS = """
DELETE FROM ref_geo.l_areas
WHERE id_type IN (SELECT id_type FROM ref_geo.bib_areas_types WHERE type_code = %s)
"""


def ref_geo_available(cursor):
    cursor.execute(
        "SELECT to_regclass('ref_geo.l_areas') IS NOT NULL "
        "AND to_regclass('ref_geo.bib_areas_types') IS NOT NULL"
    )
    return cursor.fetchone()[0]


def add_m500(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if not ref_geo_available(cursor):
            return
        cursor.execute(INSERT_TYPE, [TYPE_CODE, TYPE_CODE])
        with gzip.open(DATA_FILE, "rt", newline="") as f:
            rows = list(csv.reader(f))[1:]  # skip header
        for i in range(0, len(rows), BATCH):
            codes, wkts = zip(*rows[i : i + BATCH])
            cursor.execute(INSERT_AREAS, [list(codes), list(wkts), TYPE_CODE])


def remove_m500(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if not ref_geo_available(cursor):
            return
        cursor.execute(DELETE_AREAS, [TYPE_CODE])
        cursor.execute("DELETE FROM ref_geo.bib_areas_types WHERE type_code = %s", [TYPE_CODE])


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0007_sync_counting_object_areas_by_object"),
    ]

    operations = [
        migrations.RunPython(add_m500, remove_m500),
    ]
