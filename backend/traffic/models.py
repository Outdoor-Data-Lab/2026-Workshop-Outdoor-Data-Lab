"""App and schema "traffic": visitor counting objects and the measures they record.

Follows the TRAFFIC part of the "BDD" page of the workshop document. Units and
activities are reference tables; sources live in the "commons" app. Geometries
are stored in WGS84 (EPSG:4326).

Django has no schema option, so db_table uses the quoted form
'traffic"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

import uuid

from django.contrib.gis.db import models
from django.db.models import F, Max, Min, Q

from commons.models import DataSource

DB_SCHEMA = "traffic"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class Unit(models.Model):
    """What a measure counts (person, tent, bike...). Initial values: migration 0002."""

    id_unit = models.AutoField(primary_key=True)
    code_unit = models.CharField(max_length=50, unique=True)
    unit = models.CharField(max_length=255)

    class Meta:
        db_table = table("units")

    def __str__(self):
        return self.unit


class Activity(models.Model):
    """Practice a measure relates to (running, hiking...). Initial values: migration 0002."""

    id_activity = models.AutoField(primary_key=True)
    code_activity = models.CharField(max_length=50, unique=True)
    activity = models.CharField(max_length=255)

    class Meta:
        db_table = table("activities")
        verbose_name_plural = "activities"

    def __str__(self):
        return self.activity


class CountingObjectType(models.Model):
    id_type = models.AutoField(primary_key=True)
    code_type = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=255)

    class Meta:
        db_table = table("counting_object_types")

    def __str__(self):
        return self.type


class CountingObjectQuerySet(models.QuerySet):
    def with_data_range(self):
        """Annotate each object with the bounds of its measures (first_data, latest_data)."""
        return self.annotate(
            first_data=Min("measures__start_datetime"),
            latest_data=Max("measures__end_datetime"),
        )


class CountingObject(models.Model):
    """A counter (eco-counter, camera, ticketing...) installed somewhere."""

    id_counting_object = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    external_id = models.CharField(max_length=255, blank=True)
    type = models.ForeignKey(
        CountingObjectType,
        on_delete=models.PROTECT,
        db_column="id_type",
        related_name="counting_objects",
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        db_column="id_source",
        related_name="counting_objects",
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
            # An imported object is identified by its id in its source, so a
            # re-import updates it instead of creating a duplicate.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=~Q(external_id=""),
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
    """A count recorded by a counting object over a time interval."""

    id_measure = models.BigAutoField(primary_key=True)
    # No standalone index: the (counting_object, start_datetime) index covers it.
    counting_object = models.ForeignKey(
        CountingObject,
        on_delete=models.CASCADE,
        db_column="id_counting_object",
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
        db_column="id_unit",
        related_name="measures",
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.PROTECT,
        db_column="id_activity",
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
        ]
        indexes = [
            models.Index(fields=["counting_object", "start_datetime"]),
        ]

    def __str__(self):
        return f"{self.counting_object} {self.start_datetime:%Y-%m-%d %H:%M} : {self.count} {self.unit.code_unit}"

