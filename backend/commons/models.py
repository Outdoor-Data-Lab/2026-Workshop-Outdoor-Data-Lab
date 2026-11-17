"""App and schema "commons": data shared by every domain (sources, imports,
practice categories).

Follows the COMMONS part of the "BDD" page of the workshop document.

Naming: primary keys are Django's default "id"; reference tables have "code"
and "label"; foreign key columns use Django's default "<field>_id".

Django has no schema option, so db_table uses the quoted form
'commons"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

from django.db import models

DB_SCHEMA = "commons"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class DataSource(models.Model):
    """Where data comes from (Outdoorvision, GBIF, GeoNature...)."""

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=500)

    class Meta:
        db_table = table("data_sources")

    def __str__(self):
        return self.label


class PracticeCategory(models.Model):
    """Broad kind of practice (walking, cycling, climbing...).

    Shared by traffic (activity of a counting measure) and outdoor (category of
    a practice). Initial values: migration 0002.
    """

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)

    class Meta:
        db_table = table("practice_categories")
        verbose_name_plural = "practice categories"

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
    file = models.CharField(
        max_length=500, blank=True, help_text="Name or path of the imported file."
    )
    line_numbers = models.IntegerField(default=0)
    error_numbers = models.IntegerField(default=0)

    class Meta:
        db_table = table("data_imports")

    def __str__(self):
        return f"{self.source} {self.date_import:%Y-%m-%d %H:%M}"
