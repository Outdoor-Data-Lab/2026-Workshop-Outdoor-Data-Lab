"""Scores computed per 1 km grid cell (ref_geo "M1") from traffic.materialized_view_counts.

Each score turns the rows of the view (one per cell, source, year and month)
into ``{id_area: value}``. ``counts_queryset`` applies the shared filters
(cells, sources, year, month) so several scores can run on the same rows.
"""

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q, Sum

from ref_geo.models import LArea
from workshop2026.models import MaterializedViewCount


def _to_lambert93(geom):
    geom = GEOSGeometry(geom.wkt, srid=getattr(geom, "srid", None) or 2154)
    if geom.srid != 2154:
        geom.transform(2154)
    return geom


def counts_queryset(geoms=None, geom_ids=None, sources=None, year=None, month=None):
    """Rows of the view, filtered.

    geoms: keep the cells intersecting this geometry (any SRID, default 2154).
    geom_ids: keep these cells. With both, the union is kept; with neither,
    every cell is kept.
    """
    queryset = MaterializedViewCount.objects.all()
    if geoms is not None or geom_ids is not None:
        cells = Q(id_area__in=list(geom_ids or []))
        if geoms is not None:
            cells |= Q(
                id_area__in=LArea.objects.filter(
                    type__type_code="M1",
                    geom__intersects=_to_lambert93(geoms),
                ).values("id_area")
            )
        queryset = queryset.filter(cells)
    if sources:
        queryset = queryset.filter(id_source__in=sources)
    if year is not None:
        queryset = queryset.filter(year=year)
    if month is not None:
        queryset = queryset.filter(month=month)
    return queryset


class Score:
    """Base class: subclasses set ``name`` and implement ``compute_from``."""

    name = None

    @classmethod
    def compute(cls, geoms=None, geom_ids=None, sources=None, year=None, month=None, **params):
        queryset = counts_queryset(
            geoms=geoms, geom_ids=geom_ids, sources=sources, year=year, month=month
        )
        return cls.compute_from(queryset, **params)

    @classmethod
    def compute_from(cls, queryset, **params):
        """Return ``{id_area: score}`` for the rows of ``queryset``."""
        raise NotImplementedError


class BasicFrequentationScore(Score):
    """Sum of the counts of every source."""

    name = "basic"

    @classmethod
    def compute_from(cls, queryset, **params):
        rows = queryset.values("id_area").annotate(total=Sum("counts"))
        return {row["id_area"]: row["total"] for row in rows}


class CazalisFrequentationScore(Score):
    """Counts weighted per source: sum of counts(source) * source_weights[source]."""

    name = "cazalis"

    @classmethod
    def compute_from(cls, queryset, source_weights=None, **params):
        if source_weights is None:
            raise ValueError("source_weights must map each source ID to its weight")

        rows = queryset.values("id_area", "id_source").annotate(total=Sum("counts"))
        score_grid = {}
        for row in rows:
            source_id = row["id_source"]
            if source_id not in source_weights:
                raise ValueError(f"Missing weight for source ID {source_id}")
            area_id = row["id_area"]
            score_grid[area_id] = (
                score_grid.get(area_id, 0) + row["total"] * source_weights[source_id]
            )
        return score_grid


SCORES = {score.name: score for score in (BasicFrequentationScore, CazalisFrequentationScore)}
