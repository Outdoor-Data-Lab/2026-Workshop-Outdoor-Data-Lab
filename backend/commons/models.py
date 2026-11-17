"""App and schema "commons": data shared by every domain (sources, practices,
imports).

Follows the COMMONS part of the "BDD" page of the workshop document.

Naming: primary keys are Django's default "id"; reference tables have "code"
and "label"; foreign key columns use Django's default "<field>_id".

Django has no schema option, so db_table uses the quoted form
'commons"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

from django.db import models
from django.db.models import F, Q

DB_SCHEMA = "commons"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class DataSource(models.Model):
    """Where data comes from: a provider (OutdoorVision, GBIF...) or the
    application that produced it (Garmin, Komoot...). Initial values: migration 0002.
    """

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=500)

    class Meta:
        db_table = table("data_sources")

    def __str__(self):
        return self.label


class Practice(models.Model):
    """A practice, in a hierarchy: broad practices (walking, cycling...) have no
    parent, finer ones (hiking, mountain biking...) point to a broader one.

    Shared by traffic (practice of a counting measure) and outdoor (practice of
    an offer), which may point to any level. Initial values: migration 0002.
    """

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = table("practices")
        constraints = [
            models.CheckConstraint(
                condition=~Q(parent=F("id")),
                name="practice_not_its_own_parent",
            ),
        ]

    def __str__(self):
        return self.label


class DataImport(models.Model):
    """One run of an import from a data source."""

    date_import = models.DateTimeField(auto_now_add=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="imports",
    )
    # Uploaded file, stored under MEDIA_ROOT/imports/ (a Docker volume in dev).
    file = models.FileField(upload_to="imports", max_length=500)
    line_numbers = models.IntegerField(default=0)
    error_numbers = models.IntegerField(default=0)

    class Meta:
        db_table = table("data_imports")

    def run_parser(self):
        """Run the parser associated with this import's source, if available."""
        if self.source.code != "outdoorvision":
            return None
        if not self.pk:
            raise ValueError("Le DataImport doit être enregistré avant son traitement.")
        if not self.file:
            raise ValueError("Aucun fichier n'est associé au DataImport.")

        # Local import: the traffic parser itself imports DataImport.
        from traffic.parsers.outdoorvision import OutdoorVisionParser

        return OutdoorVisionParser(self).import_data()

    def __str__(self):
        return f"{self.source} {self.date_import:%Y-%m-%d %H:%M}"
