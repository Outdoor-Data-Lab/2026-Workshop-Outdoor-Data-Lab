"""Rename the "inpn" data source to "sinp": the observation exports it receives
come from the SINP (GeoNature synthesis), not from the INPN."""

from django.db import migrations

OLD = ("inpn", "INPN")
NEW = ("sinp", "SINP")


def rename(old, new):
    def run(apps, schema_editor):
        apps.get_model("commons", "DataSource").objects.filter(code=old[0]).update(code=new[0], label=new[1])

    return run


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0002_initial_values"),
    ]

    operations = [
        migrations.RunPython(rename(OLD, NEW), rename(NEW, OLD)),
    ]
