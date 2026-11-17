"""Initial values of the units and counting object types reference tables."""

from django.db import migrations

UNITS = [
    ("person", "Personne"),
    ("tent", "Tente"),
    ("bike", "Vélo"),
    ("vehicle", "Véhicule"),
    ("animal", "Animal"),
]

COUNTING_OBJECT_TYPES = [
    ("counter", "Compteur"),
    ("segment", "Segment"),
]

VALUES = [("Unit", UNITS), ("CountingObjectType", COUNTING_OBJECT_TYPES)]


def add_values(apps, schema_editor):
    for model_name, values in VALUES:
        model = apps.get_model("traffic", model_name)
        for code, label in values:
            model.objects.update_or_create(code=code, defaults={"label": label})


def remove_values(apps, schema_editor):
    for model_name, values in VALUES:
        apps.get_model("traffic", model_name).objects.filter(
            code__in=[code for code, _ in values]
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_values, remove_values),
    ]
