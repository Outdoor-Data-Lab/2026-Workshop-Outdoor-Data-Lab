# Outdoorvision : traces brutes (GPKG)

Une ligne du GPKG = un morceau continu d'une sortie. Les morceaux d'un même
`track_id` sont regroupés : **une sortie = un passage**.

| Colonne Outdoorvision | Destination |
|---|---|
| `track_id` | `CountingObject.external_id` |
| géométrie (morceaux réunis) | `CountingObject.geom` |
| `date_start` (min des morceaux) | `CountingMeasure.start_datetime` |
| `date_end` (max des morceaux) | `CountingMeasure.end_datetime` |
| `activity` | `CountingMeasure.practice` (code `Practice`) |
| — | `CountingMeasure.count` = 1, unité `person` |
| `id`, `user_id`, `provider`, `point_*` | non utilisés |

Le `.hdf` livré à côté (horodatage de chaque point) n'est pas utilisé.
