"""Initial values of the units and activities reference tables."""

from django.db import migrations

UNITS = [
    ("person", "Personne"),
    ("tent", "Tente"),
    ("bike", "Vélo"),
    ("vehicule", "Véhicule"),
    ("animal", "Animal"),
]

ACTIVITIES = [
    ("running", "Course à pied"),
    ("hiking", "Randonnée"),
    ("biking", "Vélo"),
    ("skiing", "Ski"),
]


def add_values(apps, schema_editor):
    Unit = apps.get_model("traffic", "Unit")
    Activity = apps.get_model("traffic", "Activity")
    for code, label in UNITS:
        Unit.objects.update_or_create(code_unit=code, defaults={"unit": label})
    for code, label in ACTIVITIES:
        Activity.objects.update_or_create(code_activity=code, defaults={"activity": label})


def remove_values(apps, schema_editor):
    apps.get_model("traffic", "Unit").objects.filter(code_unit__in=[c for c, _ in UNITS]).delete()
    apps.get_model("traffic", "Activity").objects.filter(
        code_activity__in=[c for c, _ in ACTIVITIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_values, remove_values),
    ]
