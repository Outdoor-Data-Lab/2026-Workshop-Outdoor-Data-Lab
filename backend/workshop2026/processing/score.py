"""Scores computed per 1 km grid cell (ref_geo "M1") from traffic.materialized_view_counts.

Each score turns the rows of the view (one per cell, source, year and month)
into ``{id_area: value}``. ``counts_queryset`` applies the shared filters
(cells, sources, year, month) so several scores can run on the same rows.
"""

from calendar import monthrange
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q, Sum
from math import isfinite, sqrt

from commons.models import DataSource
from ref_geo.models import LArea
from workshop2026.models import MaterializedViewCount

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
    def calculate_source_weights(cls):
        """Estimate BTA weights from summer source counts paired with ecocompteur data.

        The application stores monthly counts per M1 cell rather than the original
        BTA station-level comparison table, so correlations use paired cell-month
        observations from June to September, starting in 2021.
        """
        source_rows = list(DataSource.objects.order_by("id").values_list("id", "code"))
        source_ids = [source_id for source_id, _ in source_rows]
        reference_id = next(
            (source_id for source_id, code in source_rows if code == BTA_REFERENCE_SOURCE),
            None,
        )
        correlations = {}
        candidate_ids = {
            source_id
            for source_id, code in source_rows
            if code in BTA_WEIGHTED_SOURCES
        }
        if reference_id is None or not candidate_ids:
            return cazalis_weights_from_correlations(correlations, source_ids)

        reference_rows = list(
            MaterializedViewCount.objects.filter(
                id_source=reference_id,
                year__gte=BTA_FIRST_YEAR,
                month__in=BTA_SUMMER_MONTHS,
            ).values("id_area", "year", "month", "counts")
        )
        if not reference_rows:
            return cazalis_weights_from_correlations(correlations, source_ids)

        area_ids = {row["id_area"] for row in reference_rows}
        paired_source_rows = MaterializedViewCount.objects.filter(
            id_area__in=area_ids,
            id_source__in=candidate_ids,
            year__gte=BTA_FIRST_YEAR,
            month__in=BTA_SUMMER_MONTHS,
        ).values("id_area", "year", "month", "id_source", "counts")
        source_counts = {
            (row["id_area"], row["year"], row["month"], row["id_source"]): row["counts"]
            for row in paired_source_rows
        }

        for source_id in candidate_ids:
            reference_values = []
            source_values = []
            for row in reference_rows:
                days_in_month = monthrange(row["year"], row["month"])[1]
                key = (row["id_area"], row["year"], row["month"])
                reference_values.append(row["counts"] / days_in_month)
                source_values.append(
                    source_counts.get((*key, source_id), 0) / days_in_month
                )
            correlations[source_id] = _pearson_correlation(reference_values, source_values)

        return cazalis_weights_from_correlations(correlations, source_ids)

    @classmethod
    def compute_from(cls, queryset, source_weights=None, **params):
        if source_weights is None:
            source_weights = cls.calculate_source_weights()

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
