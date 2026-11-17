"""Initial values of the practice categories reference table."""

from django.db import migrations

PRACTICE_CATEGORIES = [
    ("hiking", "Marcher"),
    ("running", "Courir"),
    ("cycling", "Pédaler"),
    ("flying", "Voler"),
    ("boating", "Naviguer"),
    ("climbing", "Grimper"),
    ("skiing", "Skier"),
    ("riding", "Chevaucher"),
]


def add_values(apps, schema_editor):
    PracticeCategory = apps.get_model("commons", "PracticeCategory")
    for code, label in PRACTICE_CATEGORIES:
        PracticeCategory.objects.update_or_create(code=code, defaults={"label": label})


def remove_values(apps, schema_editor):
    apps.get_model("commons", "PracticeCategory").objects.filter(
        code__in=[code for code, _ in PRACTICE_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_values, remove_values),
    ]
