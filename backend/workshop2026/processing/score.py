from django.contrib.gis.geos import GEOSGeometry
from ref_geo.models import LArea
from workshop2026.models import MaterializedViewCount
from shapely import Polygon
from django.db import models


class Score:
    def compute(geoms=None, geom_ids=None, grid_size=500):
        pass


def _get_area_ids(geoms=None, geom_ids=None):
    area_ids = set(geom_ids or [])
    if geoms is not None:
        spatial_geom = GEOSGeometry(geoms.wkt)
        spatial_geom.srid = getattr(geoms, "srid", None) or 2154
        if spatial_geom.srid != 2154:
            spatial_geom.transform(2154)
        area_ids.update(
            LArea.objects.filter(
                type__type_code="M1",
                geom__intersects=spatial_geom,
            ).values_list("id_area", flat=True)
        )
    return sorted(area_ids)


class BasicFrequentationScore(Score):
    def compute(geoms=None, geom_ids=None, grid_size=500):
        area_ids = _get_area_ids(geoms=geoms, geom_ids=geom_ids)
        if not area_ids:
            return {}

        counts_by_area = (
            MaterializedViewCount.objects.filter(
                id_area__in=area_ids,
            )
            .values("id_area")
            .annotate(total=models.Sum("counts"))
        )
        return {row["id_area"]: row["total"] for row in counts_by_area}


class CazalisFrequentationScore(Score):
    def compute(geoms=None, geom_ids=None, grid_size=500, source_weights=None):
        if source_weights is None:
            raise ValueError("source_weights must map each source ID to its weight")

        area_ids = _get_area_ids(geoms=geoms, geom_ids=geom_ids)
        if not area_ids:
            return {}

        source_counts = MaterializedViewCount.objects.filter(
            id_area__in=area_ids,
        ).values("id_area", "id_source", "counts")
        score_grid = {}
        for row in source_counts:
            source_id = row["id_source"]
            if source_id not in source_weights:
                raise ValueError(f"Missing weight for source ID {source_id}")
            area_id = row["id_area"]
            score_grid[area_id] = (
                score_grid.get(area_id, 0) + row["counts"] * source_weights[source_id]
            )
        return score_grid
