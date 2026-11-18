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

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from math import isfinite
from statistics import StatisticsError, fmean, quantiles, stdev
from statistics import correlation as pearson_r

from django.contrib.gis.geos import GEOSGeometry
from django.core.cache import cache
from django.db import connection
from django.db.models import Case, Count, F, Max, Q, Sum, Value, When
from django.db.models.functions import ExtractMonth, ExtractYear, TruncDate
from django.utils import timezone

from commons.models import DataSource
from ref_geo.models import LArea
from traffic.models import CountingMeasure, CountingObject

BTA_REFERENCE_SOURCE = "ecocompteur"
# How each weighted source is matched to an eco-counter (BTA_PrepareCorrelation):
# (radius in metres, whether only the nearest object within it counts).
BTA_SOURCE_MATCHING = {
    "strava": (500, True),  # passages of the nearest edge
    "outdoorvision": (100, False),  # outings passing within 100 m
    "inaturalist": (500, False),  # observer-days within 500 m
}
BTA_SUMMER_MONTHS = (6, 7, 8, 9)
BTA_FIRST_YEAR = 2021
BTA_CORRELATION_THRESHOLD = 0.25
# A half-month (1-15, 16-end) of eco-counter data is used only with more than this many days of data.
BTA_MIN_DAYS_PER_HALF_MONTH = 10
# Scores above this quantile are capped before the 0-100 rescaling.
BTA_WINSORIZE_QUANTILE = 0.98


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
    """Pearson's r, or None when undefined (fewer than 2 points, constant input)."""
    try:
        return pearson_r(reference_values, source_values)
    except StatisticsError:
        return None


def _counts_near(station_ids, source_id, radius, nearest_only):
    """``{station id: total count}`` of the ``source_id`` objects within ``radius`` metres.

    With ``nearest_only``, only the closest object counts and stations with no
    object within ``radius`` are left out (in the R code, a counter without a
    Strava edge nearby is not used). Otherwise such stations get 0.
    """
    objects = f'"{CountingObject._meta.db_table}"'
    measures = f'"{CountingMeasure._meta.db_table}"'
    distinct = "DISTINCT ON (station.id)" if nearest_only else ""
    order = (
        "ORDER BY station.id, ST_Distance(station.geom::geography, obj.geom::geography), obj.id"
        if nearest_only
        else ""
    )
    sql = f"""
        WITH near AS (
            SELECT {distinct} station.id AS station_id, obj.id AS object_id
            FROM {objects} station
            JOIN {objects} obj
              ON obj.source_id = %(source)s
             -- A circle of radius metres drawn in Lambert-93, tested against
             -- the WGS84 geometries as they are: uses the GiST index on geom,
             -- and is ~10x faster than ST_DWithin on geography for long tracks.
             AND ST_Intersects(
                 obj.geom,
                 ST_Transform(
                     ST_Buffer(ST_Transform(station.geom, 2154), %(radius)s, 'quad_segs=32'),
                     4326
                 )
             )
            WHERE station.id = ANY(%(stations)s)
            {order}
        )
        SELECT near.station_id, COALESCE(SUM(measure.count), 0)
        FROM near
        LEFT JOIN {measures} measure ON measure.counting_object_id = near.object_id
        GROUP BY near.station_id
    """
    params = {
        "source": source_id,
        "stations": list(station_ids),
        "radius": radius,
    }
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        counts = dict(cursor.fetchall())
    if nearest_only:
        return counts
    return {station: counts.get(station, 0) for station in station_ids}


def _standardize(values):
    """z-scores with the sample standard deviation (R's ``scale``); 0 when undefined."""
    if len(values) < 2:
        return [0.0] * len(values)
    mean, sd = fmean(values), stdev(values)
    if sd == 0:
        return [0.0] * len(values)
    return [(value - mean) / sd for value in values]


def _winsorize_and_rescale(scores):
    """Cap ``{key: score}`` at the 98th percentile, then rescale it to 0-100."""
    if not scores:
        return {}
    values = list(scores.values())
    if len(values) > 1:
        # method="inclusive" matches R's default quantile (type 7).
        cap = quantiles(values, n=100, method="inclusive")[round(BTA_WINSORIZE_QUANTILE * 100) - 1]
        values = [min(value, cap) for value in values]
    low, high = min(values), max(values)
    if high == low:
        return {key: 0.0 for key in scores}
    return {key: 100 * (value - low) / (high - low) for key, value in zip(scores, values)}


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
    """Standardised frequentation of the BiodivTourAlps analysis (V. Cazalis).

    Port of ``BTA_FreqRaster`` (data/BTA-analyse-frequentation): each source's
    counts per cell are standardised (z-scores over the cells of the queryset,
    0 where a source has no data), summed with ``source_weights``, capped at the
    98th percentile and rescaled to 0-100.
    """

    name = "cazalis"

    @classmethod
    def cached_source_weights(cls):
        """``calculate_source_weights``, cached until measures or sources change.

        The calculation takes seconds on real data (the Outdoorvision tracks
        around the counters), too long to run on every API request.
        """
        measures = CountingMeasure.objects.aggregate(last=Max("id"), total=Count("id"))
        sources = DataSource.objects.aggregate(last=Max("id"), total=Count("id"))
        key = "cazalis-weights:{}:{}:{}:{}".format(
            measures["last"], measures["total"], sources["last"], sources["total"]
        )
        weights = cache.get(key)
        if weights is None:
            weights = cls.calculate_source_weights()
            cache.set(key, weights, timeout=None)
        return weights

    @classmethod
    def calculate_source_weights(cls):
        """Estimate BTA weights from correlations with the eco-counters.

        Port of ``BTA_PrepareCorrelation`` + ``BTA_PoidsRaster``: one point per
        eco-counter. Its reference value is its mean daily count over the
        summer half-months (June-September, from 2021) that have more than 10
        days of data. Each weighted source's value is its total count, over
        all periods, near the counter (see ``BTA_SOURCE_MATCHING``).

        Simplification: the R code keeps, around each counter, only the paths
        connected to its Strava edge (a 100 m corridor); here every object
        within the radius counts.
        """
        source_rows = list(DataSource.objects.order_by("id").values_list("id", "code"))
        source_ids = [source_id for source_id, _ in source_rows]
        reference_id = next(
            (source_id for source_id, code in source_rows if code == BTA_REFERENCE_SOURCE),
            None,
        )
        candidates = {
            source_id: BTA_SOURCE_MATCHING[code]
            for source_id, code in source_rows
            if code in BTA_SOURCE_MATCHING
        }
        correlations = {}
        if reference_id is None or not candidates:
            return cazalis_weights_from_correlations(correlations, source_ids)

        half_months = (
            # Not measures_queryset: its one row per (measure, cell) would count
            # twice a counter lying on the edge of two cells.
            CountingMeasure.objects.filter(
                counting_object__source_id=reference_id,
                start_datetime__gte=_start_of_day(date(BTA_FIRST_YEAR, 1, 1)),
            )
            .annotate(
                year=ExtractYear("start_datetime"),
                month=ExtractMonth("start_datetime"),
                half_month=Case(
                    When(start_datetime__day__lte=15, then=Value(1)), default=Value(2)
                ),
            )
            .filter(month__in=BTA_SUMMER_MONTHS)
            .values("counting_object_id", "year", "month", "half_month")
            .annotate(
                total=Sum("count"),
                days=Count(TruncDate("start_datetime"), distinct=True),
            )
            .filter(days__gt=BTA_MIN_DAYS_PER_HALF_MONTH)
        )
        daily_means = defaultdict(list)
        for row in half_months:
            daily_means[row["counting_object_id"]].append(row["total"] / row["days"])
        if not daily_means:
            return cazalis_weights_from_correlations(correlations, source_ids)
        reference = {station: fmean(values) for station, values in sorted(daily_means.items())}

        for source_id, (radius, nearest_only) in sorted(candidates.items()):
            near = _counts_near(reference, source_id, radius, nearest_only)
            matched = [station for station in reference if station in near]
            correlations[source_id] = _pearson_correlation(
                [reference[station] for station in matched],
                [near[station] for station in matched],
            )

        return cazalis_weights_from_correlations(correlations, source_ids)

    @classmethod
    def compute_from(cls, queryset, source_weights=None, **params):
        if source_weights is None:
            source_weights = cls.cached_source_weights()

        counts = defaultdict(dict)
        for row in queryset.values("id_area", "id_source").annotate(total=Sum("count")):
            if row["id_source"] not in source_weights:
                raise ValueError(f"Missing weight for source ID {row['id_source']}")
            counts[row["id_source"]][row["id_area"]] = row["total"]

        area_ids = sorted({id_area for by_area in counts.values() for id_area in by_area})
        raw_scores = dict.fromkeys(area_ids, 0.0)
        for source_id, by_area in counts.items():
            weight = source_weights[source_id]
            if not weight:
                continue
            z_scores = _standardize([by_area.get(id_area, 0) for id_area in area_ids])
            for id_area, z_score in zip(area_ids, z_scores):
                raw_scores[id_area] += weight * z_score
        return _winsorize_and_rescale(raw_scores)


SCORES = {score.name: score for score in (BasicFrequentationScore, CazalisFrequentationScore)}
