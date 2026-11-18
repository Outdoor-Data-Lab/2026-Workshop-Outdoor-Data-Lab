"""Materialized view of the counts per 1 km grid cell (ref_geo "M1"), source and month.

Columns (see MaterializedViewCount in workshop2026/models.py):
- counts: all measures
- count_segment: measures of "segment" counting objects
- count_presence: measures of "counter" counting objects (presence counters)

Only (cell, source, month) combinations that have measures get a row: a missing
row means 0.

The view is refreshed by statement-level triggers on traffic.counting_measures
(insert, update, delete, truncate) and traffic.counting_objects (update of the
geometry, source or type).

ref_geo is not managed by Django (loaded from the RefGeo dump), so the view is
only created when ref_geo.l_areas exists; the trigger function does nothing
while the view does not exist.

Note: fields `year` and `month` are constructed from `counting_measure.start_datetime` only
and not from `counting_measure.end_datetime`. This would bias results concerning measures
spanning through strictly more than one month or strictly more than one year. We assume
such measures to never happen or happen too few times.
"""

from django.db import migrations

CREATE_VIEW = """
DO $$
BEGIN
    IF to_regclass('ref_geo.l_areas') IS NULL
       OR to_regclass('ref_geo.bib_areas_types') IS NULL THEN
        RAISE NOTICE 'ref_geo schema missing: traffic.materialized_view_counts not created';
        RETURN;
    END IF;

    CREATE MATERIALIZED VIEW IF NOT EXISTS traffic.materialized_view_counts AS
    SELECT
        la.id_area,
        co.source_id AS id_source,
        EXTRACT(YEAR FROM cm.start_datetime)::int AS year,
        EXTRACT(MONTH FROM cm.start_datetime)::int AS month,
        SUM(cm.count) AS counts,
        COALESCE(SUM(cm.count) FILTER (WHERE cot.code = 'segment'), 0) AS count_segment,
        COALESCE(SUM(cm.count) FILTER (WHERE cot.code = 'counter'), 0) AS count_presence
    FROM ref_geo.l_areas la
    JOIN ref_geo.bib_areas_types bat ON la.id_type = bat.id_type
    JOIN traffic.counting_objects co ON ST_Intersects(la.geom_4326, co.geom)
    JOIN traffic.counting_object_types cot ON cot.id = co.type_id
    JOIN traffic.counting_measures cm ON cm.counting_object_id = co.id
    WHERE bat.type_code = 'M1'
    GROUP BY la.id_area, co.source_id, year, month;

    -- Matches the composite key of the MaterializedViewCount model, and is
    -- required by REFRESH ... CONCURRENTLY.
    CREATE UNIQUE INDEX IF NOT EXISTS materialized_view_counts_uniq
        ON traffic.materialized_view_counts (id_area, id_source, year, month);
END
$$;
"""

DROP_VIEW = "DROP MATERIALIZED VIEW IF EXISTS traffic.materialized_view_counts"

CREATE_TRIGGERS = """
CREATE OR REPLACE FUNCTION traffic.refresh_materialized_view_counts()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF to_regclass('traffic.materialized_view_counts') IS NOT NULL THEN
        REFRESH MATERIALIZED VIEW traffic.materialized_view_counts;
    END IF;
    RETURN NULL;
END
$$;

CREATE TRIGGER counting_measures_refresh_counts
    AFTER INSERT OR UPDATE OR DELETE ON traffic.counting_measures
    FOR EACH STATEMENT EXECUTE FUNCTION traffic.refresh_materialized_view_counts();

CREATE TRIGGER counting_measures_truncate_refresh_counts
    AFTER TRUNCATE ON traffic.counting_measures
    FOR EACH STATEMENT EXECUTE FUNCTION traffic.refresh_materialized_view_counts();

CREATE TRIGGER counting_objects_refresh_counts
    AFTER UPDATE OF geom, source_id, type_id ON traffic.counting_objects
    FOR EACH STATEMENT EXECUTE FUNCTION traffic.refresh_materialized_view_counts();
"""

DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS counting_objects_refresh_counts ON traffic.counting_objects;
DROP TRIGGER IF EXISTS counting_measures_truncate_refresh_counts ON traffic.counting_measures;
DROP TRIGGER IF EXISTS counting_measures_refresh_counts ON traffic.counting_measures;
DROP FUNCTION IF EXISTS traffic.refresh_materialized_view_counts();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0002_initial_values"),
        ("traffic", "0002_initial_reference_values"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_VIEW, reverse_sql=DROP_VIEW),
        migrations.RunSQL(sql=CREATE_TRIGGERS, reverse_sql=DROP_TRIGGERS),
    ]
