-- Synthetic traffic data around the Parc national des Ecrins.
-- Each of 14 M1 cells gets an ecocompteur reference and Strava,
-- Outdoorvision and iNaturalist observations for Jun-Sep, 2021-2024.
-- This creates 224 paired cell-month observations for BTA-style weights.
-- Re-runnable: only rows using demo_m1_*, demo_ecrins_* or demo_pne_* IDs
-- are replaced.
BEGIN;

DELETE FROM
    traffic.counting_measures
WHERE
    counting_object_id IN (
        SELECT
            id
        FROM
            traffic.counting_objects
        WHERE external_id LIKE 'demo_m1_%'
           OR external_id LIKE 'demo_ecrins_%'
           OR external_id LIKE 'demo_pne_%'
    );

DELETE FROM
    traffic.counting_objects
WHERE external_id LIKE 'demo_m1_%'
   OR external_id LIKE 'demo_ecrins_%'
   OR external_id LIKE 'demo_pne_%';

-- The coordinates are representative trail locations in the Ecrins. Each is
-- snapped to its nearest M1 cell; geometry is stored in WGS84 (EPSG:4326).
CREATE TEMPORARY TABLE demo_sites ON COMMIT DROP AS
WITH proposed_sites (
    site_code, site_name, longitude, latitude, eco_daily,
    strava_factor, outdoor_factor, inat_base, inat_factor,
    variation, practice_code
) AS (
    VALUES
        ('vallouise', 'Vallouise', 6.49::double precision, 44.83::double precision, 165, 0.82::numeric, 0.68::numeric, 14, 0.10::numeric, 1, 'hiking'),
        ('ailefroide', 'Ailefroide', 6.41::double precision, 44.90::double precision, 245, 0.93::numeric, 0.57::numeric, 23, 0.08::numeric, 4, 'mountaineering'),
        ('berarde', 'La Berarde', 6.28::double precision, 44.93::double precision, 132, 0.69::numeric, 0.86::numeric, 10, 0.13::numeric, 7, 'mountaineering'),
        ('lauvitel', 'Lac du Lauvitel', 6.04::double precision, 45.05::double precision, 198, 0.88::numeric, 0.74::numeric, 21, 0.09::numeric, 2, 'hiking'),
        ('lautaret', 'Col du Lautaret', 6.41::double precision, 45.04::double precision, 174, 1.12::numeric, 0.95::numeric, 18, 0.07::numeric, 9, 'cycling'),
        ('valgaudemar', 'Valgaudemar', 6.18::double precision, 44.81::double precision, 82, 0.74::numeric, 0.48::numeric, 8, 0.11::numeric, 3, 'hiking'),
        ('dormillouse', 'Dormillouse', 6.45::double precision, 44.78::double precision, 116, 0.64::numeric, 0.72::numeric, 12, 0.08::numeric, 11, 'hiking'),
        ('grave', 'La Grave', 6.30::double precision, 45.05::double precision, 214, 1.21::numeric, 0.98::numeric, 22, 0.06::numeric, 5, 'mountain_biking'),
        ('pre_mme_carle', 'Pre de Madame Carle', 6.37::double precision, 44.91::double precision, 276, 1.06::numeric, 0.83::numeric, 28, 0.05::numeric, 8, 'hiking'),
        ('gioberney', 'Gioberney', 6.42::double precision, 44.82::double precision, 143, 0.81::numeric, 0.55::numeric, 15, 0.10::numeric, 6, 'hiking'),
        ('etages', 'Les Etages', 6.27::double precision, 44.88::double precision, 101, 0.71::numeric, 0.67::numeric, 9, 0.12::numeric, 10, 'mountaineering'),
        ('champoleon', 'Champoleon', 6.28::double precision, 44.74::double precision, 73, 0.59::numeric, 0.43::numeric, 7, 0.12::numeric, 12, 'hiking'),
        ('prapic', 'Prapic', 6.33::double precision, 44.72::double precision, 108, 0.85::numeric, 0.64::numeric, 13, 0.09::numeric, 5, 'hiking'),
        ('venosc', 'Venosc', 6.12::double precision, 45.02::double precision, 232, 1.28::numeric, 1.08::numeric, 24, 0.06::numeric, 3, 'cycling')
)
SELECT
    site.*,
    area.id_area,
    area.geom
FROM proposed_sites site
CROSS JOIN LATERAL (
    SELECT la.id_area, la.geom
    FROM ref_geo.l_areas la
    JOIN ref_geo.bib_areas_types bat ON la.id_type = bat.id_type
    WHERE bat.type_code = 'M1'
      AND la.geom IS NOT NULL
      AND la.geom_4326 && ST_Expand(
          ST_SetSRID(ST_MakePoint(site.longitude, site.latitude), 4326),
          0.025
      )
    ORDER BY ST_Distance(
        la.geom,
        ST_Transform(
            ST_SetSRID(ST_MakePoint(site.longitude, site.latitude), 4326),
            2154
        )
    )
    LIMIT 1
) area;

WITH source_types(source_code, type_code, source_offset) AS (
    VALUES
        ('ecocompteur', 'counter', 0),
        ('strava', 'segment', 1),
        ('outdoorvision', 'segment', 2),
        ('inaturalist', 'counter', 3)
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
    'demo_pne_' || site.site_code || '_' || source.source_code,
    (
        SELECT
            id
        FROM
            traffic.counting_object_types
        WHERE code = source.type_code
    ),
    (
        SELECT
            id
        FROM
            commons.data_sources
        WHERE code = source.source_code
    ),
    NULL,
    CASE
        WHEN source.type_code = 'segment' THEN ST_Transform(
            ST_MakeLine(
                ST_Translate(ST_PointOnSurface(site.geom), -100, -100),
                ST_Translate(ST_PointOnSurface(site.geom), 100, 100)
            ),
            4326
        )
        ELSE ST_Transform(ST_PointOnSurface(site.geom), 4326)
    END,
    now(),
    now(),
    DATE '2021-06-01',
    NULL,
    FALSE,
    'Demo PNE - ' || site.site_name,
    ''
FROM
    demo_sites site
    CROSS JOIN source_types source;

-- Four source series per site, monthly in summer for four years. The source
-- rates share a site-level signal with distinct ratios and small deterministic
-- noise so the correlations are reproducible and non-identical.
WITH source_types(source_code, source_offset) AS (
    VALUES
        ('ecocompteur', 0),
        ('strava', 1),
        ('outdoorvision', 2),
        ('inaturalist', 3)
), summer_months AS (
    SELECT
        month_start::date AS month_start,
        EXTRACT(YEAR FROM month_start)::integer AS year,
        EXTRACT(MONTH FROM month_start)::integer AS month,
        EXTRACT(DAY FROM (date_trunc('month', month_start) + INTERVAL '1 month' - INTERVAL '1 day'))::integer AS days_in_month,
        CASE EXTRACT(MONTH FROM month_start)::integer
            WHEN 6 THEN 0.80::numeric
            WHEN 7 THEN 1.20::numeric
            WHEN 8 THEN 1.12::numeric
            ELSE 0.72::numeric
        END AS season_factor,
        1 + (EXTRACT(YEAR FROM month_start)::integer - 2021) * 0.025 AS year_factor
    FROM GENERATE_SERIES(DATE '2021-06-01', DATE '2024-09-01', INTERVAL '1 month') AS month_start
    WHERE EXTRACT(MONTH FROM month_start)::integer IN (6, 7, 8, 9)
)
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
    counting_object.id,
    counting_object.external_id || '_' || to_char(summer.month_start, 'YYYYMM'),
    now(),
    now(),
    summer.month_start::timestamp,
    (summer.month_start + INTERVAL '1 month')::timestamp,
    GREATEST(1, ROUND((CASE source.source_code
        WHEN 'ecocompteur' THEN site.eco_daily
        WHEN 'strava' THEN site.eco_daily * site.strava_factor
        WHEN 'outdoorvision' THEN site.eco_daily * site.outdoor_factor
        ELSE site.inat_base + site.eco_daily * site.inat_factor
    END * summer.season_factor * summer.year_factor
        + MOD(site.variation + summer.year * 3 + summer.month * 7 + source.source_offset * 5, 11) - 5
    )::numeric)::integer) * summer.days_in_month,
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
            code = site.practice_code
    ),
    FALSE
FROM
    demo_sites site
    CROSS JOIN source_types source
    CROSS JOIN summer_months summer
    JOIN traffic.counting_objects counting_object
        ON counting_object.external_id = 'demo_pne_' || site.site_code || '_' || source.source_code;

COMMIT;

REFRESH MATERIALIZED VIEW traffic.materialized_view_counts;

-- Check: demo row count and correlation-input coverage.
SELECT
    COUNT(DISTINCT counting_object.id) AS demo_objects,
    COUNT(measure.id) AS demo_measures,
    COUNT(DISTINCT measure.counting_object_id) FILTER (
        WHERE source.code = 'ecocompteur'
    ) AS ecocompteur_sites
FROM traffic.counting_objects counting_object
JOIN commons.data_sources source ON source.id = counting_object.source_id
LEFT JOIN traffic.counting_measures measure ON measure.counting_object_id = counting_object.id
WHERE counting_object.external_id LIKE 'demo_pne_%';