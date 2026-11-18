"""App and schema "outdoor": outdoor offers (trails, climbing sites, via ferratas...).

Follows the OUTDOOR part of the "BDD" page of the workshop document. Practices
and data sources live in the "commons" app. Geometries are stored in WGS84
(EPSG:4326).

Naming: primary keys are Django's default "id"; foreign key columns use
Django's default "<field>_id".

Django has no schema option, so db_table uses the quoted form
'outdoor"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

from django.contrib.gis.db import models
from django.db.models import Q

from commons.models import DataImport, DataSource, Practice

DB_SCHEMA = "outdoor"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class Offer(models.Model):
    """Something to practise outdoors: a trail, a climbing site, a ski slope..."""

    # Given by the source when it has one, never generated.
    uuid = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    external_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    geom = models.GeometryField(srid=4326)
    # Any level of the practice hierarchy (e.g. "climbing" or "via_ferrata").
    practice = models.ForeignKey(
        Practice,
        on_delete=models.PROTECT,
        related_name="offers",
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="offers",
    )
    # The last import that wrote the offer (created or updated it): deleting
    # that import deletes the offer. Empty for an offer not imported.
    data_import = models.ForeignKey(
        DataImport,
        on_delete=models.CASCADE,
        related_name="offers",
        null=True,
        blank=True,
    )
    date_create = models.DateTimeField(auto_now_add=True)
    date_update = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = table("offers")
        constraints = [
            # An imported offer is identified by its id in its source, so a
            # re-import updates it instead of creating a duplicate.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=~Q(external_id=""),
                name="offer_unique_external_id",
            ),
        ]

    def __str__(self):
        return self.name


class OfferImport(DataImport):
    """An import of offers (see parsers.OfferParser): the admin page of the offer
    imports, which offers the sources of the outdoor domain."""

    class Meta:
        proxy = True
