"""Initial values of the taxonomic referentials table."""

from django.db import migrations

REFERENTIALS = [
    ("taxref", "TaxRef"),
    ("gbif", "GBIF Backbone Taxonomy"),
    ("col", "Catalogue of Life"),
    ("worms", "WoRMS"),
]


def add_values(apps, schema_editor):
    TaxonomicReferential = apps.get_model("biodiversity", "TaxonomicReferential")
    for code, label in REFERENTIALS:
        TaxonomicReferential.objects.update_or_create(
            code=code, defaults={"label": label}
        )


def remove_values(apps, schema_editor):
    apps.get_model("biodiversity", "TaxonomicReferential").objects.filter(
        code__in=[c for c, _ in REFERENTIALS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("biodiversity", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_values, remove_values),
    ]
