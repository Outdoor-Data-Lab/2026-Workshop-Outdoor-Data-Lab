"""App and schema "traffic": visitor counting objects and the measures they record.

Follows the TRAFFIC part of the "BDD" page of the workshop document. Units are
a reference table; sources and practices (the practice of a measure)
live in the "commons" app. Geometries are stored in WGS84 (EPSG:4326).

Naming: primary keys are Django's default "id"; reference tables have "code"
and "label"; foreign key columns use Django's default "<field>_id".

Django has no schema option, so db_table uses the quoted form
'traffic"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

import uuid

from django.contrib.gis.db import models
from django.contrib.gis.db.models.functions import Transform
from django.contrib.postgres.indexes import GistIndex
from django.db.models import F, Func, Max, Min, Q, Value

from commons.models import DataImport, DataSource, Practice
from ref_geo.models import BibAreasType, LArea

DB_SCHEMA = "traffic"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class Unit(models.Model):
    """What a measure counts (person, tent, bike...). Initial values: migration 0002."""

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)

    class Meta:
        db_table = table("units")

    def __str__(self):
        return self.label


class CountingObjectType(models.Model):
    """Counter, segment... Initial values: migration 0002."""

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)

    class Meta:
        db_table = table("counting_object_types")

    def __str__(self):
        return self.label


class CountingObjectQuerySet(models.QuerySet):
    def with_data_range(self):
        """Annotate each object with the bounds of its measures (first_data, latest_data)."""
        return self.annotate(
            first_data=Min("measures__start_datetime"),
            latest_data=Max("measures__end_datetime"),
        )


class CountingObject(models.Model):
    """A counter (automatic counter, camera, ticketing...) installed somewhere."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    external_id = models.CharField(max_length=255, blank=True)
    type = models.ForeignKey(
        CountingObjectType,
        on_delete=models.PROTECT,
        related_name="counting_objects",
    )
    # Provider: the application that supplied the data to us (e.g. OutdoorVision).
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="counting_objects",
    )
    # Origin: the application that produced the data in the first place, when
    # the provider aggregates others (e.g. Garmin, Komoot behind OutdoorVision).
    # Empty when the provider is the producer, or when the origin is unknown.
    origin = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="originated_counting_objects",
        null=True,
        blank=True,
    )
    geom = models.GeometryField(srid=4326)
    # For the vector tiles (traffic/tiles): web mercator, simplified to 10 m
    # (Outdoorvision tracks: 40 million points, 8 once simplified).
    geom_tiles = models.GeneratedField(
        expression=Func(
            Transform("geom", 3857),
            Value(10),
            function="ST_SimplifyPreserveTopology",
            output_field=models.GeometryField(srid=3857),
        ),
        output_field=models.GeometryField(srid=3857, spatial_index=False),
        db_persist=True,
    )
    # The import that created the object. Deleting it deletes the object when no
    # measure of another import is left on it (see signals.py); otherwise the
    # object stays, unlinked.
    data_import = models.ForeignKey(
        DataImport,
        on_delete=models.SET_NULL,
        related_name="counting_objects",
        null=True,
        blank=True,
    )
    date_create = models.DateTimeField(auto_now_add=True)
    date_update = models.DateTimeField(auto_now=True)
    installation_date = models.DateField(null=True, blank=True)
    uninstallation_date = models.DateField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    manager = models.CharField(max_length=255, blank=True)
    image_url = models.URLField(max_length=500, blank=True)

    objects = CountingObjectQuerySet.as_manager()

    class Meta:
        db_table = table("counting_objects")
        indexes = [GistIndex(fields=["geom_tiles"], name="counting_object_geom_tiles")]
        constraints = [
            # An imported object is identified by its id in its provider and its
            # origin, so a re-import updates it instead of creating a duplicate.
            # The same segment seen through Garmin and through Komoot gives two
            # objects. An empty origin counts as a value (nulls_distinct=False).
            models.UniqueConstraint(
                fields=["source", "origin", "external_id"],
                condition=~Q(external_id=""),
                nulls_distinct=False,
                name="counting_object_unique_external_id",
            ),
            models.CheckConstraint(
                condition=Q(uninstallation_date__isnull=True)
                | Q(installation_date__isnull=True)
                | Q(uninstallation_date__gte=F("installation_date")),
                name="counting_object_uninstallation_after_installation",
            ),
        ]

    def __str__(self):
        return self.external_id or str(self.uuid)


class CountingMeasure(models.Model):
    """A count recorded by a counting object over a time interval.

    An object may have measures of different lengths over the same period (a
    Strava edge gets a yearly measure and daily ones): do not add up its
    measures without choosing one length.
    """

    # No standalone index: the index of counting_measure_unique_key, which starts
    # with (counting_object, start_datetime), covers it.
    counting_object = models.ForeignKey(
        CountingObject,
        on_delete=models.CASCADE,
        db_index=False,
        related_name="measures",
    )
    external_id = models.CharField(max_length=255, blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    count = models.IntegerField()
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="measures",
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.PROTECT,
        related_name="measures",
        null=True,
        blank=True,
    )
    # The import that wrote the measure: deleting it deletes the measure.
    data_import = models.ForeignKey(
        DataImport,
        on_delete=models.CASCADE,
        related_name="counting_measures",
        null=True,
        blank=True,
    )
    date_create = models.DateTimeField(auto_now_add=True)
    date_update = models.DateTimeField(auto_now=True)
    processed = models.BooleanField(default=False)

    class Meta:
        db_table = table("counting_measures")
        constraints = [
            models.CheckConstraint(
                condition=Q(end_datetime__gt=F("start_datetime")),
                name="counting_measure_end_after_start",
            ),
            # One measure per object, period, practice and unit: a re-import
            # replaces it. A measure without practice counts as one value.
            models.UniqueConstraint(
                fields=["counting_object", "start_datetime", "end_datetime", "practice", "unit"],
                nulls_distinct=False,
                name="counting_measure_unique_key",
            ),
        ]

    def __str__(self):
        return f"{self.counting_object} {self.start_datetime:%Y-%m-%d %H:%M} : {self.count} {self.unit.code}"


class CountingObjectArea(models.Model):
    """A 1 km grid cell (ref_geo "M1") intersected by a counting object.

    Filled by a trigger on traffic.counting_objects (insert, update of geom),
    see migration 0003, and rebuilt with ``manage.py sync_counting_object_areas``
    (e.g. after loading ref_geo). A segment crossing several cells gets a row
    per cell: its measures count in each of them.

    ``area`` references ref_geo.l_areas (column ``id_area``) without a database
    constraint: ref_geo is loaded outside of Django, possibly after ``migrate``,
    and may be reloaded.
    """

    pk = models.CompositePrimaryKey("counting_object", "area")
    counting_object = models.ForeignKey(
        CountingObject,
        on_delete=models.CASCADE,
        db_index=False,
        related_name="areas",
    )
    area = models.ForeignKey(
        LArea,
        on_delete=models.CASCADE,
        db_constraint=False,
        db_column="id_area",
        related_name="counting_object_areas",
    )
    # Copied from ref_geo.l_areas.id_type: selecting a grid needs no join.
    area_type = models.ForeignKey(
        BibAreasType,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        db_column="id_type",
        related_name="+",
        null=True,
        blank=True,
    )
    # Metres of a line object inside the cell (NULL for points): the scores
    # weight the counts by it, as the R analysis does.
    length_m = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = table("counting_object_areas")
        indexes = [
            models.Index(fields=["area_type", "area", "counting_object"], name="coa_type_area_object"),
        ]


class CellDayCount(models.Model):
    """Precomputed counts per (grid cell, source, day), see ``refresh_cell_day_counts``.

    One row replaces every measure of a source in a cell on a day (in the
    TIME_ZONE of the database session), so the scores aggregate this table instead
    of joining millions of measures to the cell links. Rebuilt as a whole by
    ``manage.py refresh_cell_counts`` and after each traffic import. The scores
    use it only while ``CellCountsState`` is not stale
    (workshop2026.processing.score.counts_are_fresh), else they read the measures.
    Field names are those of the per-row annotations of ``measures_queryset``.
    """

    area_type = models.ForeignKey(
        BibAreasType, on_delete=models.DO_NOTHING, db_constraint=False,
        db_column="id_type", related_name="+",
    )
    id_area = models.IntegerField()
    id_source = models.IntegerField()
    day = models.DateField()
    count = models.BigIntegerField()
    # count x km of the object inside the cell (1 km for points), see length_weighted_count.
    weighted = models.FloatField()
    n_segment = models.BigIntegerField()  # count of "segment" objects
    n_presence = models.BigIntegerField()  # count of "counter" objects
    first_start = models.DateTimeField()
    last_start = models.DateTimeField()

    class Meta:
        db_table = table("cell_day_counts")
        constraints = [
            models.UniqueConstraint(
                fields=["area_type", "id_area", "id_source", "day"], name="cell_day_count_key"
            ),
        ]
        indexes = [models.Index(fields=["area_type", "day"], name="cell_day_count_period")]


class CellCountsState(models.Model):
    """One row (id 1): whether CellDayCount is out of date.

    ``stale`` is set by triggers on the measures and the object/cell links
    (migration 0012) and cleared by ``traffic.refresh_cell_day_counts()``.
    """

    stale = models.BooleanField(default=True)
    refreshed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = table("cell_day_counts_state")


class TrafficImport(DataImport):
    """An import of counting objects and measures (see traffic.parsers): the admin page
    of the traffic imports, which offers the traffic formats and sources only."""

    class Meta:
        proxy = True
