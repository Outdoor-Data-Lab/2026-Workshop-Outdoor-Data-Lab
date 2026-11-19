"""Counts and scores per grid cell (ref_geo type ``area_type``, DEFAULT_GRID_AREA_TYPE by default), computed on the fly
from the measures.

A measure belongs to the cells its counting object intersects
(traffic.counting_object_areas): a segment crossing several cells counts in
each of them. ``measures_queryset`` applies the shared filters (cells, sources,
period) and annotates each measure with ``id_area`` and ``id_source``, so
several scores can run on the same rows. Each score turns those rows into
``{id_area: value}``.

A measure belongs to the period [date_from, date_to] when its ``start_datetime``
falls in it, both dates included, in the current time zone (TIME_ZONE setting);
to ``months`` (1 to 12, e.g. 12, 1, 2 for the winters of every year) when the
month of its ``start_datetime`` is one of them.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from math import isfinite
from statistics import StatisticsError, fmean, quantiles, stdev
from statistics import correlation as pearson_r

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.cache import cache
from django.db import connection
from django.db.models import Case, Count, F, FloatField, Max, Min, Q, Subquery, Sum, Value, When
from django.db.models.functions import Cast, ExtractMonth, ExtractYear, TruncDate
from django.utils import timezone

from commons.models import DataSource
from ref_geo.models import BibAreasType, LArea
from traffic.models import (
    CellCountsState,
    CellDayCount,
    CountingMeasure,
    CountingObject,
    CountingObjectArea,
)

BTA_REFERENCE_SOURCE = "ecocompteur"
# How each weighted source is matched to an eco-counter (BTA_PrepareCorrelation):
# (radius in metres, whether only the nearest object within it counts, whether
# each count is multiplied by the km of its object: R's DistPers).
BTA_SOURCE_MATCHING = {
    "strava": (500, True, False),  # passages of the nearest edge
    "outdoorvision": (100, False, True),  # DistPers of the segments within 100 m
    "inaturalist": (500, False, False),  # observer-days within 500 m
}
# Eco-counters (external_id) left out of the weight estimation. CARRELET was
# already excluded by the R code; PREMCARL (Pré de Madame Carle, reached by car)
# counts 4 times more than any other counter for few Strava passages, and alone
# brings the Strava correlation from 0.80 down to 0.04.
BTA_EXCLUDED_COUNTERS = frozenset({"CARRELET", "PREMCARL"})
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


def _counts_near(station_ids, source_id, radius, nearest_only, length_weighted=False):
    """``{station id: total count}`` of the ``source_id`` objects within ``radius`` metres.

    With ``length_weighted``, each count is multiplied by the length in km of its
    object (R's ``DistPers = count x Length_km``, not only the part within
    ``radius``): its part in the grid ``DEFAULT_GRID_AREA_TYPE``, from the stored
    link lengths, else its whole length.

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
    links = f'"{CountingObjectArea._meta.db_table}"'
    # The km of the object inside the grid, summed from the stored lengths of its
    # cells (no geometry work); ST_Length of the whole object while they are missing.
    km = (
        f"""COALESCE(
                (SELECT SUM(coa.length_m) FROM {links} coa
                 WHERE coa.counting_object_id = obj.id
                   AND coa.id_type = (SELECT id_type FROM ref_geo.bib_areas_types
                                      WHERE type_code = %(grid)s)) / 1000.0,
                ST_Length(obj.geom::geography) / 1000.0
            )::float8"""
        if length_weighted
        else "1.0::float8"
    )
    sql = f"""
        WITH near AS (
            SELECT {distinct} station.id AS station_id, obj.id AS object_id,
                   {km} AS km
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
        SELECT near.station_id, COALESCE(SUM(measure.count * near.km), 0)
        FROM near
        LEFT JOIN {measures} measure ON measure.counting_object_id = near.object_id
        GROUP BY near.station_id
    """
    params = {
        "source": source_id,
        "stations": list(station_ids),
        "radius": radius,
        "grid": settings.DEFAULT_GRID_AREA_TYPE,
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


def _filter_cells(queryset, geoms, geom_ids, area_type):
    if geoms is not None or geom_ids is not None:
        cells = Q(id_area__in=list(geom_ids or []))
        if geoms is not None:
            cells |= Q(
                id_area__in=LArea.objects.filter(
                    type__type_code=area_type,
                    geom__intersects=_to_lambert93(geoms),
                ).values("id_area")
            )
        queryset = queryset.filter(cells)
    return queryset


def _area_type_id(area_type):
    return Subquery(BibAreasType.objects.filter(type_code=area_type).values("pk")[:1])


def _length_in_km():
    """Km of the object inside the cell, 1 for a point (no length)."""
    return Case(
        When(area_length_m__isnull=True, then=Value(1.0)),
        default=F("area_length_m") / 1000.0,
        output_field=FloatField(),
    )


def measures_queryset(
    geoms=None, geom_ids=None, sources=None, date_from=None, date_to=None, area_type=None,
    months=None,
):
    """Measures, one row per (measure, cell), annotated for the scores.

    Annotations (the same fields as ``CellDayCount``, see ``scored_rows``):
    ``id_area``, ``id_source``, ``weighted`` (count x km of the object inside
    the cell, 1 km for a point: as in the R analysis, BTA_PrepareStrava, a
    segment weighs by the part of it that is in the cell, not as a whole in
    every cell it touches), ``n_segment`` / ``n_presence`` (count of "segment" /
    "counter" objects), ``first_start`` and ``last_start``.

    geoms: keep the cells intersecting this geometry (any SRID, default 2154).
    geom_ids: keep these cells. With both, the union is kept; with neither,
    every cell is kept.
    date_from, date_to: ``datetime.date``, both included.
    months: months of the year (1 to 12) to keep, whatever the year.
    area_type: ref_geo type_code of the grid (default ``settings.DEFAULT_GRID_AREA_TYPE``).
    """
    area_type = area_type or settings.DEFAULT_GRID_AREA_TYPE
    queryset = CountingMeasure.objects.annotate(
        id_area=F("counting_object__areas__area_id"),
        id_source=F("counting_object__source_id"),
        # Same join as id_area: counting_object_areas holds every grid of
        # AREA_TYPES, with the type of each cell (no join on ref_geo).
        id_area_type=F("counting_object__areas__area_type_id"),
        # Metres of the object inside the cell; NULL for points.
        area_length_m=F("counting_object__areas__length_m"),
    ).filter(id_area__isnull=False, id_area_type=_area_type_id(area_type))
    queryset = queryset.annotate(
        weighted=Cast("count", FloatField()) * _length_in_km(),
        n_segment=Case(
            When(counting_object__type__code="segment", then=F("count")), default=0
        ),
        n_presence=Case(
            When(counting_object__type__code="counter", then=F("count")), default=0
        ),
        first_start=F("start_datetime"),
        last_start=F("start_datetime"),
    )
    queryset = _filter_cells(queryset, geoms, geom_ids, area_type)
    if sources:
        queryset = queryset.filter(id_source__in=sources)
    # Bounds on start_datetime itself (not start_datetime__date), so the
    # (counting_object, start_datetime) index is used.
    if date_from is not None:
        queryset = queryset.filter(start_datetime__gte=_start_of_day(date_from))
    if date_to is not None:
        queryset = queryset.filter(start_datetime__lt=_start_of_day(date_to + timedelta(days=1)))
    if months:
        queryset = queryset.filter(start_datetime__month__in=months)
    return queryset


def cell_counts_queryset(
    geoms=None, geom_ids=None, sources=None, date_from=None, date_to=None, area_type=None,
    months=None,
):
    """Same filters and fields as ``measures_queryset``, on the precomputed ``CellDayCount``.

    One row per (cell, source, day) instead of one per (measure, cell). The
    period is on ``day``: the date of ``start_datetime`` in the session time zone.
    """
    area_type = area_type or settings.DEFAULT_GRID_AREA_TYPE
    queryset = CellDayCount.objects.filter(area_type_id=_area_type_id(area_type))
    queryset = _filter_cells(queryset, geoms, geom_ids, area_type)
    if sources:
        queryset = queryset.filter(id_source__in=sources)
    if date_from is not None:
        queryset = queryset.filter(day__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(day__lte=date_to)
    if months:
        queryset = queryset.filter(day__month__in=months)
    return queryset


def counts_version():
    """When ``CellDayCount`` was refreshed (ISO string), or None if it is stale.

    A cache key for anything computed from the data: it changes at each refresh,
    and there is none while the counts are stale (a write since the refresh).
    """
    refreshed_at = (
        CellCountsState.objects.filter(stale=False).values_list("refreshed_at", flat=True).first()
    )
    return refreshed_at.isoformat() if refreshed_at else None


def counts_are_fresh():
    """Whether ``CellDayCount`` is up to date (no write to the measures or links since its refresh)."""
    return counts_version() is not None


def scored_rows(**filters):
    """The rows the scores read: the precomputed counts when they are fresh, else the measures.

    Both give the same results (``cell_counts_queryset`` is much smaller); the
    precomputed one is rebuilt by ``manage.py refresh_cell_counts`` and after each
    traffic import. ``**filters`` are those of ``measures_queryset``.
    """
    if counts_are_fresh():
        return cell_counts_queryset(**filters)
    return measures_queryset(**filters)


def counts_by_area(measures):
    """``{id_area: {"counts", "count_segment", "count_presence", "sources"}}`` for ``measures``.

    count_segment: measures of "segment" objects; count_presence: measures of
    "counter" objects (presence counters); sources: ``[{"id", "code", "label",
    "absolute", "count", "first_data", "latest_data", "length_km", "person_km"}]``,
    the counts per data source and the start of their first and last measures;
    length_km: km of the source's line objects inside the cell (any period, from
    the stored link lengths), person_km: sum of count x km over ``measures``; both
    None for sources without line objects in the cell. Two grouped queries.
    """
    rows = measures.values("id_area", "id_source").annotate(
        total=Sum("count"),
        person_km=Sum("weighted"),
        segment=Sum("n_segment"),
        presence=Sum("n_presence"),
        first_data=Min("first_start"),
        latest_data=Max("last_start"),
    )
    sources = {
        source.pk: source
        for source in DataSource.objects.only("code", "label", "absolute_counts")
    }
    rows = list(rows)
    lengths = {
        (row["area_id"], row["counting_object__source_id"]): row["total"] / 1000
        for row in CountingObjectArea.objects.filter(
            area_id__in={row["id_area"] for row in rows}, length_m__isnull=False
        )
        .values("area_id", "counting_object__source_id")
        .annotate(total=Sum("length_m"))
    }
    counts = {}
    for row in rows:
        length_km = lengths.get((row["id_area"], row["id_source"]))
        area = counts.setdefault(
            row["id_area"], {"counts": 0, "count_segment": 0, "count_presence": 0, "sources": []}
        )
        area["counts"] += row["total"]
        area["count_segment"] += row["segment"]
        area["count_presence"] += row["presence"]
        source = sources[row["id_source"]]
        area["sources"].append(
            {
                "id": row["id_source"],
                "code": source.code,
                "label": source.label,
                "absolute": source.absolute_counts,
                "count": row["total"],
                "first_data": row["first_data"],
                "latest_data": row["latest_data"],
                "length_km": length_km,
                "person_km": row["person_km"] if length_km is not None else None,
            }
        )
    for area in counts.values():
        area["sources"].sort(key=lambda source: source["label"])
    return counts


class Score:
    """Base class: subclasses set ``name`` and implement ``compute_from``."""

    name = None

    @classmethod
    def compute(
        cls, geoms=None, geom_ids=None, sources=None, date_from=None, date_to=None,
        area_type=None, months=None, **params
    ):
        queryset = scored_rows(
            geoms=geoms, geom_ids=geom_ids, sources=sources,
            date_from=date_from, date_to=date_to, area_type=area_type, months=months,
        )
        return cls.compute_from(queryset, **params)

    @classmethod
    def compute_from(cls, queryset, **params):
        """Return ``{id_area: score}`` for the rows of ``queryset`` (see scored_rows)."""
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
    98th percentile and rescaled to 0-100. The counts are weighted by the length of
    the segment inside each cell (the ``weighted`` field of the rows).
    """

    name = "cazalis"

    @classmethod
    def cached_source_weights(cls):
        """``calculate_source_weights``, cached (see ``cached_estimate``)."""
        return cls.cached_estimate()["weights"]

    @classmethod
    def cached_estimate(cls):
        """``estimate_source_weights``, cached until measures or sources change.

        The calculation takes seconds on real data (the Outdoorvision tracks
        around the counters), too long to run on every API request.
        """
        sources = DataSource.objects.aggregate(last=Max("id"), total=Count("id"))
        version = counts_version()
        if version:  # no need to count the measures
            key = f"cazalis-weights:{version}:{sources['last']}:{sources['total']}"
        else:
            measures = CountingMeasure.objects.aggregate(last=Max("id"), total=Count("id"))
            key = "cazalis-weights:{}:{}:{}:{}".format(
                measures["last"], measures["total"], sources["last"], sources["total"]
            )
        estimate = cache.get(key)
        if estimate is None:
            estimate = cls.estimate_source_weights()
            cache.set(key, estimate, timeout=None)
        return estimate

    @classmethod
    def calculate_source_weights(cls):
        """``{source id: weight}``, see ``estimate_source_weights``."""
        return cls.estimate_source_weights()["weights"]

    @classmethod
    def estimate_source_weights(cls):
        """Estimate BTA weights from correlations with the eco-counters.

        Counters of ``BTA_EXCLUDED_COUNTERS`` are left out.

        Returns ``{"weights": {source id: weight}, "counters": n, "correlations":
        {source id: {"r": Pearson's r or None, "counters": n}}}``: ``counters``
        is the number of eco-counters with enough data, and per source the
        number of them matched to it (all of them, except for a nearest-only
        source such as Strava). ``correlations`` holds the weighted sources only.

        Port of ``BTA_PrepareCorrelation`` + ``BTA_PoidsRaster``: one point per
        eco-counter. Its reference value is its mean daily count over the
        summer half-months (June-September, from 2021) that have more than 10
        days of data. Each weighted source's value is its total count, over
        all periods, near the counter (see ``BTA_SOURCE_MATCHING``; Outdoorvision
        counts are multiplied by the km of their object, as in R).

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

        def result(counters=0):
            return {
                "weights": cazalis_weights_from_correlations(
                    {source_id: c["r"] for source_id, c in correlations.items()}, source_ids
                ),
                "counters": counters,
                "correlations": correlations,
            }

        if reference_id is None or not candidates:
            return result()

        half_months = (
            # Not measures_queryset: its one row per (measure, cell) would count
            # twice a counter lying on the edge of two cells.
            CountingMeasure.objects.filter(
                counting_object__source_id=reference_id,
                start_datetime__gte=_start_of_day(date(BTA_FIRST_YEAR, 1, 1)),
            )
            .exclude(counting_object__external_id__in=BTA_EXCLUDED_COUNTERS)
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
            return result()
        reference = {station: fmean(values) for station, values in sorted(daily_means.items())}

        for source_id, (radius, nearest_only, length_weighted) in sorted(candidates.items()):
            near = _counts_near(reference, source_id, radius, nearest_only, length_weighted)
            matched = [station for station in reference if station in near]
            correlations[source_id] = {
                "r": _pearson_correlation(
                    [reference[station] for station in matched],
                    [near[station] for station in matched],
                ),
                "counters": len(matched),
            }

        return result(counters=len(reference))

    @classmethod
    def compute_from(cls, queryset, source_weights=None, **params):
        if source_weights is None:
            source_weights = cls.cached_source_weights()

        counts = defaultdict(dict)
        for row in queryset.values("id_area", "id_source").annotate(total=Sum("weighted")):
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
