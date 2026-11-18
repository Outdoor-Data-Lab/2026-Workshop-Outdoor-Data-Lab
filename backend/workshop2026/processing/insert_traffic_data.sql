-- Fake traffic data to test the counts and scores per 1 km grid cell.
-- The cells of the objects (traffic.counting_object_areas) are filled by
-- the triggers of migration traffic 0003.
-- Re-runnable: the demo rows (external_id 'demo_m1_%') are deleted first.
--
-- Run (from the repo root):
--   docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < backend/workshop2026/processing/insert_traffic_data.sql
--
-- What it covers, on the first 3 M1 cells (by id_area):
--   cell 1: outdoorvision counter + outdoorvision segment  -> count_presence and count_segment on one row
--           ecocompteur counter                            -> a second source in the same cell
--   cell 2: komoot segment                                 -> count_segment only
--   cell 3: strava counter, measures in 2023 and 2024      -> several years
-- Measures: one per day on the 5th, 15th and 25th of each month, Jan-Mar,
-- count = object number * 10 + day of month (easy to check by hand).
BEGIN;

DELETE FROM
    traffic.counting_measures
WHERE
    counting_object_id IN (
        SELECT
            id
        FROM
            traffic.counting_objects
        WHERE
            external_id LIKE 'demo_m1_%'
    );

DELETE FROM
    traffic.counting_object_areas
WHERE
    counting_object_id IN (
        SELECT
            id
        FROM
            traffic.counting_objects
        WHERE
            external_id LIKE 'demo_m1_%'
    );

DELETE FROM
    traffic.counting_objects
WHERE
    external_id LIKE 'demo_m1_%';

-- Grid geometries are in EPSG:2154; traffic stores EPSG:4326.
WITH sample_areas AS (
    SELECT
        la.id_area,
        la.geom,
        ROW_NUMBER() OVER (
            ORDER BY
                la.id_area
        ) AS position
    FROM
        ref_geo.l_areas la
        JOIN ref_geo.bib_areas_types bat ON la.id_type = bat.id_type
    WHERE
        bat.type_code = 'M1'
        AND la.geom IS NOT NULL
    ORDER BY
        la.id_area
    LIMIT
        3
), sample_objects AS (
    SELECT
        *
    FROM
        (
            VALUES
                ('demo_m1_001', 'counter', 'outdoorvision', 1),
                ('demo_m1_002', 'segment', 'outdoorvision', 1),
                ('demo_m1_003', 'counter', 'ecocompteur', 1),
                ('demo_m1_004', 'segment', 'komoot', 2),
                ('demo_m1_005', 'counter', 'strava', 3)
        ) AS s(external_id, type_code, source_code, position)
)
INSERT INTO
    traffic.counting_objects (
        uuid,
        external_id,
        type_id,
        source_id,
        origin_id,
        geom,
        date_create,
        date_update,
        installation_date,
        uninstallation_date,
        processed,
        manager,
        image_url
    )
SELECT
    gen_random_uuid(),
    s.external_id,
    (
        SELECT
            id
        FROM
            traffic.counting_object_types
        WHERE
            code = s.type_code
    ),
    (
        SELECT
            id
        FROM
            commons.data_sources
        WHERE
            code = s.source_code
    ),
    NULL,
    -- Kept well inside the 1 km cell so it intersects that cell only.
    CASE
        WHEN s.type_code = 'segment' THEN ST_Transform(
            ST_MakeLine(
                ST_Translate(ST_PointOnSurface(a.geom), -100, -100),
                ST_Translate(ST_PointOnSurface(a.geom), 100, 100)
            ),
            4326
        )
        ELSE ST_Transform(ST_PointOnSurface(a.geom), 4326)
    END,
    now(),
    now(),
    '2022-06-01' :: date,
    NULL,
    FALSE,
    'Équipe de démonstration',
    ''
FROM
    sample_objects s
    JOIN sample_areas a ON a.position = s.position;

INSERT INTO
    traffic.counting_measures (
        counting_object_id,
        external_id,
        date_create,
        date_update,
        start_datetime,
        end_datetime,
        count,
        unit_id,
        practice_id,
        processed
    )
SELECT
    co.id,
    co.external_id || '_' || to_char(d, 'YYYYMMDD'),
    now(),
    now(),
    d + interval '8 hours',
    d + interval '18 hours',
    substr(co.external_id, 9) :: int * 10 + extract(
        day
        FROM
            d
    ) :: int,
    (
        SELECT
            id
        FROM
            traffic.units
        WHERE
            code = 'person'
    ),
    (
        SELECT
            id
        FROM
            commons.practices
        WHERE
            code = 'hiking'
    ),
    FALSE
FROM
    traffic.counting_objects co
    CROSS JOIN LATERAL (
        SELECT
            (make_date(y, m, day)) :: timestamptz AS d
        FROM
            generate_series(
                2023,
                CASE
                    WHEN co.external_id = 'demo_m1_005' THEN 2024
                    ELSE 2023
                END
            ) y,
            generate_series(1, 3) m,
            unnest(ARRAY [5, 15, 25]) day
    ) days
WHERE
    co.external_id LIKE 'demo_m1_%';

COMMIT;

-- Check: counts per cell, source and month of the demo measures.
SELECT
    coa.id_area,
    co.source_id AS id_source,
    EXTRACT(YEAR FROM cm.start_datetime)::int AS year,
    EXTRACT(MONTH FROM cm.start_datetime)::int AS month,
    SUM(cm.count) AS counts
FROM
    traffic.counting_measures cm
    JOIN traffic.counting_objects co ON co.id = cm.counting_object_id
    JOIN traffic.counting_object_areas coa ON coa.counting_object_id = co.id
WHERE
    co.external_id LIKE 'demo_m1_%'
GROUP BY
    1, 2, 3, 4
ORDER BY
    1, 2, 3, 4;
