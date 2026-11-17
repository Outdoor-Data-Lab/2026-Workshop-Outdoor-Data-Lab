CREATE MATERIALIZED VIEW traffic.materialized_view_counts AS
WITH grid_sources AS (
    SELECT la.id_area, ds.id AS id_source
    FROM ref_geo.l_areas la
    JOIN ref_geo.bib_areas_types bat ON la.id_type = bat.id_type
    CROSS JOIN commons.data_sources ds
    WHERE bat.type_code = 'M1'
), area_source_counts AS (
    SELECT
        la.id_area,
        co.source_id AS id_source,
        SUM(cm.count) AS counts
    FROM ref_geo.l_areas la
    JOIN ref_geo.bib_areas_types bat ON la.id_type = bat.id_type
    JOIN traffic.counting_objects co ON ST_Intersects(la.geom_4326, co.geom)
    JOIN traffic.counting_measures cm ON cm.counting_object_id = co.id
    WHERE bat.type_code = 'M1'
    GROUP BY la.id_area, co.source_id
)
SELECT
    gs.id_area,
    gs.id_source,
    COALESCE(ascs.counts, 0) AS counts
FROM grid_sources gs
LEFT JOIN area_source_counts ascs
    ON ascs.id_area = gs.id_area
    AND ascs.id_source = gs.id_source;