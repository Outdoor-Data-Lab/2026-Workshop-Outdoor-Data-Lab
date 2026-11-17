"""Initial values of the counting object types reference table."""

from django.db import migrations

COUNTING_OBJECT_TYPES = [
    ("counter", "Compteur"),
    ("segment", "Segment"),
]


def add_values(apps, schema_editor):
    CountingObjectType = apps.get_model("traffic", "CountingObjectType")
    for code, label in COUNTING_OBJECT_TYPES:
        CountingObjectType.objects.update_or_create(
            code_type=code, defaults={"type": label}
        )


def remove_values(apps, schema_editor):
    apps.get_model("traffic", "CountingObjectType").objects.filter(
        code_type__in=[c for c, _ in COUNTING_OBJECT_TYPES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("traffic", "0002_initial_units_activities"),
    ]

    operations = [
        migrations.RunPython(add_values, remove_values),
    ]
