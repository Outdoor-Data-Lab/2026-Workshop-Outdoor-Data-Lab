"""App and schema "biodiversity": species observations and habitat records.

Follows the BIODIVERSITÉ part of the "BDD" page of the workshop document.
Taxons (TaxHub), statuses (BDC) and Habref are not modelled yet: cd_ref and
cd_hab are plain codes for now. Sources live in the "commons" app.
Geometries are stored in WGS84 (EPSG:4326).

Django has no schema option, so db_table uses the quoted form
'biodiversity"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

import uuid

from django.contrib.gis.db import models
from django.db.models import F, Q

from commons.models import DataImport, DataSource

DB_SCHEMA = "biodiversity"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class TaxonomicReferential(models.Model):
    """Referential an original taxon id belongs to (TaxRef, GBIF, COL, WoRMS).

    Initial values: migration 0002.
    """

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)

    class Meta:
        db_table = table("taxonomic_referentials")

    def __str__(self):
        return self.label


class TaxonRecord(models.Model):
    """An observation of a taxon (a species occurrence)."""

    # Identifier of the observation in its source (SINP uuid, GBIF
    # occurrence...) when it has one, generated otherwise.
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="taxon_records",
    )
    # TaxRef reference name; null when the original taxon has no TaxRef match.
    cd_ref = models.IntegerField(null=True, blank=True)
    # Taxon id as given by the source, in the referential below.
    original_id_taxon = models.CharField(max_length=100)
    referential = models.ForeignKey(
        TaxonomicReferential,
        on_delete=models.PROTECT,
        related_name="taxon_records",
    )
    scientific_name = models.CharField(max_length=500)
    record_start_date = models.DateField()
    record_end_date = models.DateField()
    geom = models.GeometryField(srid=4326)
    # Precision of the location, including any deliberate degradation.
    coordinate_uncertainty_in_meters = models.PositiveIntegerField(
        null=True, blank=True
    )
    dataset_uuid = models.UUIDField(null=True, blank=True)
    # The last import that wrote the record, created or updated: deleting that
    # import deletes the record.
    data_import = models.ForeignKey(
        DataImport,
        on_delete=models.CASCADE,
        related_name="taxon_records",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = table("taxon_records")
        constraints = [
            models.CheckConstraint(
                condition=Q(record_end_date__gte=F("record_start_date")),
                name="taxon_record_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.scientific_name} {self.record_start_date:%Y-%m-%d}"


class HabitatStation(models.Model):
    """A place where habitats were described (Occhab station)."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="habitat_stations",
    )
    geom = models.GeometryField(srid=4326)

    class Meta:
        db_table = table("habitat_stations")

    def __str__(self):
        return str(self.uuid)


class HabitatRecord(models.Model):
    """A habitat observed on a station (Occhab habitat)."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    station = models.ForeignKey(
        HabitatStation,
        on_delete=models.CASCADE,
        related_name="habitat_records",
    )
    # Habref habitat code.
    cd_hab = models.IntegerField()
    community_interest = models.BooleanField(default=False)

    class Meta:
        db_table = table("habitat_records")

    def __str__(self):
        return f"{self.station} : {self.cd_hab}"


class ObservationImport(DataImport):
    """An import of taxon records (see biodiversity.parsers): the admin page of the
    biodiversity imports, which offers the biodiversity formats and sources only."""

    class Meta:
        proxy = True
