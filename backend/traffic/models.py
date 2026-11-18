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
from django.db.models import F, Max, Min, Q

from commons.models import DataSource, Practice

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


# Key of a measure (see counting_measure_unique_period): the parsers upsert on it.
MEASURE_KEY = ["counting_object", "start_datetime", "end_datetime", "practice", "unit"]


class CountingMeasure(models.Model):
    """A count recorded by a counting object over a time interval.

    An object may have measures of different lengths over the same period (a
    Strava edge gets a yearly measure and daily ones): do not add up its
    measures without choosing one length.
    """

    # No standalone index: the counting_measure_unique_period index starts with it.
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
            # One count per object, period, practice and unit: a re-import updates
            # it instead of adding a duplicate. An empty practice counts as a value.
            models.UniqueConstraint(
                fields=MEASURE_KEY,
                nulls_distinct=False,
                name="counting_measure_unique_period",
            ),
        ]

    def __str__(self):
        return f"{self.counting_object} {self.start_datetime:%Y-%m-%d %H:%M} : {self.count} {self.unit.code}"

