-- Données fictives autour du massif des Écrins pour tester les cartes de score.
-- Exécution réentrante : seules les lignes portant les identifiants de démo
-- de ce script sont remplacées.
BEGIN;

DELETE FROM traffic.counting_measures
WHERE counting_object_id IN (
    SELECT id
    FROM traffic.counting_objects
    WHERE external_id IN (
        'demo_m1_001', 'demo_m1_002', 'demo_m1_003',
        'demo_ecrins_vallouise', 'demo_ecrins_ailefroide',
        'demo_ecrins_berarde', 'demo_ecrins_lauvitel',
        'demo_ecrins_lautaret', 'demo_ecrins_valgaudemar',
        'demo_ecrins_dormillouse', 'demo_ecrins_grave',
        'demo_ecrins_plateau', 'demo_ecrins_alpinisme'
    )
);

DELETE FROM traffic.counting_objects
WHERE external_id IN (
    'demo_m1_001', 'demo_m1_002', 'demo_m1_003',
    'demo_ecrins_vallouise', 'demo_ecrins_ailefroide',
    'demo_ecrins_berarde', 'demo_ecrins_lauvitel',
    'demo_ecrins_lautaret', 'demo_ecrins_valgaudemar',
    'demo_ecrins_dormillouse', 'demo_ecrins_grave',
    'demo_ecrins_plateau', 'demo_ecrins_alpinisme'
);

-- Chaque point de démo est rattaché à la maille M1 la plus proche.
-- Les géométries sont construites en Lambert-93 puis stockées en WGS84.
CREATE TEMPORARY TABLE demo_sites ON COMMIT DROP AS
WITH proposed_sites (
    external_id, site_name, type_code, source_code, origin_code,
    unit_code, practice_code, weekday_count, weekend_factor,
    variation, longitude, latitude, installation_date
) AS (
    VALUES
        ('demo_ecrins_vallouise', 'Vallouise', 'counter', 'ecocompteur', NULL, 'person', 'hiking', 155, 1.9, 1, 6.49::double precision, 44.83::double precision, DATE '2021-06-15'),
        ('demo_ecrins_ailefroide', 'Ailefroide', 'counter', 'ecocompteur', NULL, 'person', 'hiking', 230, 2.1, 4, 6.41::double precision, 44.90::double precision, DATE '2020-07-01'),
        ('demo_ecrins_berarde', 'La Bérarde', 'counter', 'outdoorvision', 'garmin', 'person', 'mountaineering', 82, 1.7, 7, 6.28::double precision, 44.93::double precision, DATE '2022-05-20'),
        ('demo_ecrins_lauvitel', 'Lac du Lauvitel', 'counter', 'strava', NULL, 'person', 'hiking', 105, 1.8, 2, 6.04::double precision, 45.05::double precision, DATE '2023-04-10'),
        ('demo_ecrins_lautaret', 'Col du Lautaret', 'segment', 'outdoorvision', 'komoot', 'bike', 'cycling', 180, 2.2, 9, 6.41::double precision, 45.04::double precision, DATE '2021-05-01'),
        ('demo_ecrins_valgaudemar', 'Valgaudemar', 'counter', 'geotrek', NULL, 'person', 'hiking', 68, 2.0, 3, 6.18::double precision, 44.81::double precision, DATE '2022-06-01'),
        ('demo_ecrins_dormillouse', 'Dormillouse', 'counter', 'ecocompteur', NULL, 'person', 'hiking', 74, 2.3, 11, 6.45::double precision, 44.78::double precision, DATE '2020-07-15'),
        ('demo_ecrins_grave', 'La Grave', 'segment', 'strava', NULL, 'bike', 'mountain_biking', 132, 1.8, 5, 6.30::double precision, 45.05::double precision, DATE '2023-05-15'),
        ('demo_ecrins_plateau', 'Plateau d’Emparis', 'counter', 'geotrek', NULL, 'person', 'trail_running', 48, 1.6, 8, 6.12::double precision, 45.02::double precision, DATE '2021-08-01'),
        ('demo_ecrins_alpinisme', 'Vallon des Étançons', 'counter', 'outdoorvision', 'garmin', 'person', 'mountaineering', 92, 1.5, 6, 6.32::double precision, 44.91::double precision, DATE '2022-07-01')
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
          0.05
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

INSERT INTO traffic.counting_objects (
    uuid, external_id, type_id, source_id, origin_id, geom,
    date_create, date_update, installation_date, uninstallation_date,
    processed, manager, image_url
)
SELECT
    gen_random_uuid(),
    site.external_id,
    (SELECT id FROM traffic.counting_object_types WHERE code = site.type_code),
    (SELECT id FROM commons.data_sources WHERE code = site.source_code),
    (SELECT id FROM commons.data_sources WHERE code = site.origin_code),
    CASE WHEN site.type_code = 'segment' THEN
        ST_Transform(ST_MakeLine(
            ST_ClosestPoint(site.geom, ST_Translate(ST_PointOnSurface(site.geom), -80, -40)),
            ST_ClosestPoint(site.geom, ST_Translate(ST_PointOnSurface(site.geom), 80, 40))
        ), 4326)
    ELSE ST_Transform(ST_PointOnSurface(site.geom), 4326) END,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    site.installation_date,
    NULL,
    FALSE,
    'Démonstration · ' || site.site_name,
    'https://example.com/outdoor-data-lab/' || site.external_id || '.jpg'
FROM demo_sites site;

-- Deux semaines de fréquentation journalière, avec des pics le week-end
-- et des profils distincts selon les lieux et les pratiques.
INSERT INTO traffic.counting_measures (
    counting_object_id, external_id, date_create, date_update,
    start_datetime, end_datetime, count, unit_id, practice_id, processed
)
SELECT
    counting_object.id,
    site.external_id || '_' || TO_CHAR(calendar.measure_day, 'YYYYMMDD'),
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    calendar.measure_day::date::timestamp,
    (calendar.measure_day::date + 1)::timestamp,
    ROUND((site.weekday_count * CASE
        WHEN EXTRACT(ISODOW FROM calendar.measure_day) IN (6, 7)
            THEN site.weekend_factor
        ELSE 1
    END)::numeric)::integer
        + MOD(EXTRACT(DOY FROM calendar.measure_day)::integer + site.variation, 17),
    (SELECT id FROM traffic.units WHERE code = site.unit_code),
    (SELECT id FROM commons.practices WHERE code = site.practice_code),
    FALSE
FROM demo_sites site
JOIN traffic.counting_objects counting_object
    ON counting_object.external_id = site.external_id
CROSS JOIN GENERATE_SERIES(
    DATE '2025-07-07', DATE '2025-07-20', INTERVAL '1 day'
) AS calendar(measure_day);

REFRESH MATERIALIZED VIEW traffic.materialized_view_counts;

COMMIT;