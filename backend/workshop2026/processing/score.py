"""Counts and scores per 1 km grid cell (ref_geo "M1"), computed on the fly
from the measures.

A measure belongs to the cells its counting object intersects
(traffic.counting_object_areas): a segment crossing several cells counts in
each of them. ``measures_queryset`` applies the shared filters (cells, sources,
period) and annotates each measure with ``id_area`` and ``id_source``, so
several scores can run on the same rows. Each score turns those rows into
``{id_area: value}``.

A measure belongs to the period [date_from, date_to] when its ``start_datetime``
falls in it, both dates included, in the current time zone (TIME_ZONE setting).
"""

from datetime import datetime, time, timedelta

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import F, Q, Sum
from django.utils import timezone

from ref_geo.models import LArea
from traffic.models import CountingMeasure


def _to_lambert93(geom):
    geom = GEOSGeometry(geom.wkt, srid=getattr(geom, "srid", None) or 2154)
    if geom.srid != 2154:
        geom.transform(2154)
    return geom


def _start_of_day(date):
    return datetime.combine(date, time.min, tzinfo=timezone.get_current_timezone())


def measures_queryset(geoms=None, geom_ids=None, sources=None, date_from=None, date_to=None):
    """Measures, one row per (measure, cell), annotated with ``id_area`` and ``id_source``.

    geoms: keep the cells intersecting this geometry (any SRID, default 2154).
    geom_ids: keep these cells. With both, the union is kept; with neither,
    every cell is kept.
    date_from, date_to: ``datetime.date``, both included.
    """
    queryset = CountingMeasure.objects.annotate(
        id_area=F("counting_object__areas__area_id"),
        id_source=F("counting_object__source_id"),
    ).filter(id_area__isnull=False)
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
    # Bounds on start_datetime itself (not start_datetime__date), so the
    # (counting_object, start_datetime) index is used.
    if date_from is not None:
        queryset = queryset.filter(start_datetime__gte=_start_of_day(date_from))
    if date_to is not None:
        queryset = queryset.filter(start_datetime__lt=_start_of_day(date_to + timedelta(days=1)))
    return queryset


def counts_by_area(measures):
    """``{id_area: {"counts", "count_segment", "count_presence"}}`` for ``measures``.

    count_segment: measures of "segment" objects; count_presence: measures of
    "counter" objects (presence counters).
    """
    rows = measures.values("id_area").annotate(
        counts=Sum("count"),
        count_segment=Sum("count", filter=Q(counting_object__type__code="segment"), default=0),
        count_presence=Sum("count", filter=Q(counting_object__type__code="counter"), default=0),
    )
    return {row.pop("id_area"): row for row in rows}


class Score:
    """Base class: subclasses set ``name`` and implement ``compute_from``."""

    name = None

    @classmethod
    def compute(
        cls, geoms=None, geom_ids=None, sources=None, date_from=None, date_to=None, **params
    ):
        queryset = measures_queryset(
            geoms=geoms, geom_ids=geom_ids, sources=sources,
            date_from=date_from, date_to=date_to,
        )
        return cls.compute_from(queryset, **params)

    @classmethod
    def compute_from(cls, queryset, **params):
        """Return ``{id_area: score}`` for the rows of ``queryset`` (see measures_queryset)."""
        raise NotImplementedError


class BasicFrequentationScore(Score):
    """Sum of the counts of every source."""

    name = "basic"

    @classmethod
    def compute_from(cls, queryset, **params):
        rows = queryset.values("id_area").annotate(total=Sum("count"))
        return {row["id_area"]: row["total"] for row in rows}


class CazalisFrequentationScore(Score):
    """Counts weighted per source: sum of counts(source) * source_weights[source]."""

    name = "cazalis"

    @classmethod
    def compute_from(cls, queryset, source_weights=None, **params):
        if source_weights is None:
            raise ValueError("source_weights must map each source ID to its weight")

        rows = queryset.values("id_area", "id_source").annotate(total=Sum("count"))
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
