-- Script SQL pour insérer des données fictives dans les tables de traffic
-- Basé sur les modèles traffic/models.py

-- ============================================
-- Table: traffic.counting_objects
-- ============================================
-- Les géométries des mailles sont en EPSG:2154. Les exemples sont placés
-- dans ces mailles puis transformés en EPSG:4326, le SRID attendu par traffic.
WITH sample_areas AS (
    SELECT
        la.id_area,
        la.geom,
        ROW_NUMBER() OVER (ORDER BY la.id_area) AS position
    FROM ref_geo.l_areas la
    JOIN ref_geo.bib_areas_types bat ON la.id_type = bat.id_type
    WHERE bat.type_code = 'M1'
      AND la.geom IS NOT NULL
    ORDER BY la.id_area
    LIMIT 3
), sample_objects AS (
    SELECT * FROM (VALUES
        ('demo_m1_001', 'counter', 'outdoorvision', 1, '2020-01-15'::date, 'Équipe de démonstration', 'https://example.com/demo/001.jpg'),
        ('demo_m1_002', 'counter', 'outdoorvision', 2, '2021-03-20'::date, 'Équipe de démonstration', 'https://example.com/demo/002.jpg'),
        ('demo_m1_003', 'segment', 'komoot', 3, '2019-11-10'::date, 'Équipe de démonstration', 'https://example.com/demo/003.jpg')
    ) AS sample(external_id, type_code, source_code, position, installation_date, manager, image_url)
)
INSERT INTO traffic.counting_objects (
    uuid, external_id, type_id, source_id, origin_id, geom, date_create, date_update, installation_date, uninstallation_date, processed, manager, image_url
)
SELECT
    uuid_generate_v4(),
    sample.external_id,
    (SELECT id FROM traffic.counting_object_types WHERE code = sample.type_code),
    (SELECT id FROM commons.data_sources WHERE code = sample.source_code),
    NULL,
    CASE WHEN sample.type_code = 'segment' THEN
        ST_Transform(ST_MakeLine(
            ST_ClosestPoint(area.geom, ST_Translate(ST_PointOnSurface(area.geom), -20, -20)),
            ST_ClosestPoint(area.geom, ST_Translate(ST_PointOnSurface(area.geom), 20, 20))
        ), 4326)
    ELSE ST_Transform(ST_PointOnSurface(area.geom), 4326) END,
    sample.installation_date,
    sample.installation_date,
    sample.installation_date,
    NULL,
    FALSE,
    sample.manager,
    sample.image_url
FROM sample_objects sample
JOIN sample_areas area ON area.position = sample.position;

-- ============================================
-- Table: traffic.counting_measures
-- ============================================
INSERT INTO traffic.counting_measures (
    counting_object_id, external_id, date_create, date_update, start_datetime, end_datetime, count, unit_id, practice_id, processed
) VALUES
    -- Mesures pour le compteur de démonstration 1
    ((SELECT id FROM traffic.counting_objects WHERE external_id = 'demo_m1_001'), 'demo_m1_001_20230101', 
     '2023-01-01 00:00:00', '2023-01-01 23:59:59', '2023-01-01 00:00:00', '2023-01-01 23:59:59', 45, (SELECT id FROM traffic.units WHERE code = 'person'), NULL, FALSE),
    
    ((SELECT id FROM traffic.counting_objects WHERE external_id = 'demo_m1_001'), 'demo_m1_001_20230102', 
     '2023-01-02 00:00:00', '2023-01-02 23:59:59', '2023-01-02 00:00:00', '2023-01-02 23:59:59', 62, (SELECT id FROM traffic.units WHERE code = 'person'), (SELECT id FROM commons.practices WHERE code = 'walking'), FALSE),
    
    -- Mesures pour le compteur de démonstration 2
    ((SELECT id FROM traffic.counting_objects WHERE external_id = 'demo_m1_002'), 'demo_m1_002_20230101', 
     '2023-01-01 00:00:00', '2023-01-01 23:59:59', '2023-01-01 00:00:00', '2023-01-01 23:59:59', 12, (SELECT id FROM traffic.units WHERE code = 'tent'), NULL, FALSE),
    
    -- Mesures pour l'objet de démonstration 3
    ((SELECT id FROM traffic.counting_objects WHERE external_id = 'demo_m1_003'), 'demo_m1_003_20230101', 
     '2023-01-01 00:00:00', '2023-01-01 23:59:59', '2023-01-01 00:00:00', '2023-01-01 23:59:59', 87, (SELECT id FROM traffic.units WHERE code = 'bike'), (SELECT id FROM commons.practices WHERE code = 'running'), FALSE),
    
    ((SELECT id FROM traffic.counting_objects WHERE external_id = 'demo_m1_003'), 'demo_m1_003_20230102', 
     '2023-01-02 00:00:00', '2023-01-02 23:59:59', '2023-01-02 00:00:00', '2023-01-02 23:59:59', 95, (SELECT id FROM traffic.units WHERE code = 'bike'), (SELECT id FROM commons.practices WHERE code = 'running'), FALSE);