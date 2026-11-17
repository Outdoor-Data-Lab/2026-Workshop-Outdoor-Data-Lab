"""App and schema "commons": data shared by every domain (sources, imports).

Follows the COMMONS part of the "BDD" page of the workshop document.

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

    id_source = models.AutoField(primary_key=True)
    code_source = models.CharField(max_length=50, unique=True)
    source = models.CharField(max_length=500)

    class Meta:
        db_table = table("data_sources")

    def __str__(self):
        return self.source


class DataImport(models.Model):
    """One run of an import from a data source."""

    id_import = models.AutoField(primary_key=True)
    date_import = models.DateTimeField(auto_now_add=True)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        db_column="id_source",
        related_name="imports",
    )
    line_numbers = models.IntegerField(default=0)
    error_numbers = models.IntegerField(default=0)

    class Meta:
        db_table = table("data_imports")

    def __str__(self):
        return f"{self.source} {self.date_import:%Y-%m-%d %H:%M}"
