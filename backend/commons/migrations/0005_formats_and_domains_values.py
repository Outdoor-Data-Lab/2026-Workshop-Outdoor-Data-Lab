"""Domains of the initial sources, and format of the imports made before formats
existed (the parser was then chosen by the source code)."""

from django.db import migrations

SOURCE_DOMAINS = {
    "outdoorvision": ["traffic"],
    "strava": ["traffic"],
    "ecocompteur": ["traffic"],
    "inaturalist": ["traffic", "biodiversity"],
    "sinp": ["biodiversity"],
    "gbif": ["biodiversity"],
    "geonature": ["biodiversity"],
    "geotrek": ["outdoor"],
    "visorando": ["outdoor"],
    # garmin, komoot: origins only.
}
# Source code -> format of its imports; any other source imported offers.
SOURCE_FORMATS = {
    "outdoorvision": "outdoorvision",
    "strava": "strava",
    "ecocompteur": "counter",
    "inaturalist": "inaturalist",
    "sinp": "sinp",
    "gbif": "gbif",
}
FORMAT_DOMAINS = {
    "outdoorvision": "traffic",
    "strava": "traffic",
    "counter": "traffic",
    "inaturalist": "traffic",
    "sinp": "biodiversity",
    "gbif": "biodiversity",
    "offers": "outdoor",
}


def set_values(apps, schema_editor):
    DataSource = apps.get_model("commons", "DataSource")
    DataImport = apps.get_model("commons", "DataImport")
    for code, domains in SOURCE_DOMAINS.items():
        DataSource.objects.filter(code=code).update(domains=domains)
    for data_import in DataImport.objects.select_related("source"):
        data_import.format = SOURCE_FORMATS.get(data_import.source.code, "offers")
        data_import.save(update_fields=["format"])
        # A source added by hand keeps being offered where it was imported.
        source = data_import.source
        domain = FORMAT_DOMAINS[data_import.format]
        if domain not in source.domains:
            source.domains = [*source.domains, domain]
            source.save(update_fields=["domains"])


def clear_values(apps, schema_editor):
    apps.get_model("commons", "DataSource").objects.update(domains=[])
    apps.get_model("commons", "DataImport").objects.update(format="")


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0004_dataimport_format_datasource_domains"),
    ]

    operations = [
        migrations.RunPython(set_values, clear_values),
    ]
