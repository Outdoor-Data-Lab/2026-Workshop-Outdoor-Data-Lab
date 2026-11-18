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

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from math import isfinite, sqrt

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import F, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils import timezone

from commons.models import DataSource
from ref_geo.models import LArea
from traffic.models import CountingMeasure

BTA_REFERENCE_SOURCE = "ecocompteur"
BTA_WEIGHTED_SOURCES = {"strava", "inaturalist", "outdoorvision"}
BTA_SUMMER_MONTHS = (6, 7, 8, 9)
BTA_FIRST_YEAR = 2021
BTA_CORRELATION_THRESHOLD = 0.25


def cazalis_weights_from_correlations(correlations, source_ids):
    """Apply the BTA correlation-to-weight rule and apportion 100 integer points."""
    raw_weights = {}
    for source_id in source_ids:
        correlation = correlations.get(source_id)
        if correlation is None or not isfinite(correlation) or correlation <= BTA_CORRELATION_THRESHOLD:
            raw_weights[source_id] = 0.0
        else:
            raw_weights[source_id] = 1 / (1 - min(correlation, 0.99))

    total = sum(raw_weights.values())
    if total == 0:
        return {source_id: 0 for source_id in source_ids}

    percentages = {source_id: weight / total * 100 for source_id, weight in raw_weights.items()}
    weights = {source_id: int(percentages[source_id]) for source_id in source_ids}
    remainder = 100 - sum(weights.values())
    order = sorted(
        source_ids,
        key=lambda source_id: (-(percentages[source_id] - weights[source_id]), source_id),
    )
    for source_id in order[:remainder]:
        weights[source_id] += 1
    return weights


def _pearson_correlation(reference_values, source_values):
    if len(reference_values) < 2:
        return None
    reference_mean = sum(reference_values) / len(reference_values)
    source_mean = sum(source_values) / len(source_values)
    reference_delta = [value - reference_mean for value in reference_values]
    source_delta = [value - source_mean for value in source_values]
    denominator = sqrt(
        sum(value**2 for value in reference_delta)
        * sum(value**2 for value in source_delta)
    )
    if denominator == 0:
        return None
    return sum(x_value * y_value for x_value, y_value in zip(reference_delta, source_delta)) / denominator


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
    def calculate_source_weights(cls):
        """Estimate BTA weights from summer source counts paired with ecocompteur data.

        The original BTA method compares counts per station; here correlations
        use paired (M1 cell, month) observations from June to September,
        starting in 2021, as daily averages.
        """
        source_rows = list(DataSource.objects.order_by("id").values_list("id", "code"))
        source_ids = [source_id for source_id, _ in source_rows]
        reference_id = next(
            (source_id for source_id, code in source_rows if code == BTA_REFERENCE_SOURCE),
            None,
        )
        candidate_ids = {
            source_id for source_id, code in source_rows if code in BTA_WEIGHTED_SOURCES
        }
        correlations = {}
        if reference_id is None or not candidate_ids:
            return cazalis_weights_from_correlations(correlations, source_ids)

        monthly = (
            measures_queryset(
                sources=[reference_id, *candidate_ids], date_from=date(BTA_FIRST_YEAR, 1, 1)
            )
            .annotate(
                year=ExtractYear("start_datetime"), month=ExtractMonth("start_datetime")
            )
            .filter(month__in=BTA_SUMMER_MONTHS)
            .values("id_area", "id_source", "year", "month")
            .annotate(total=Sum("count"))
        )
        counts = {
            (row["id_area"], row["year"], row["month"], row["id_source"]): row["total"]
            for row in monthly
        }
        reference_keys = sorted(
            key[:3] for key in counts if key[3] == reference_id
        )
        if not reference_keys:
            return cazalis_weights_from_correlations(correlations, source_ids)

        for source_id in candidate_ids:
            reference_values = []
            source_values = []
            for key in reference_keys:
                days_in_month = monthrange(key[1], key[2])[1]
                reference_values.append(counts[(*key, reference_id)] / days_in_month)
                source_values.append(counts.get((*key, source_id), 0) / days_in_month)
            correlations[source_id] = _pearson_correlation(reference_values, source_values)

        return cazalis_weights_from_correlations(correlations, source_ids)

    @classmethod
    def compute_from(cls, queryset, source_weights=None, **params):
        if source_weights is None:
            source_weights = cls.calculate_source_weights()

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
