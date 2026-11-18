from django.db import migrations, models


def set_absolute(apps, schema_editor):
    apps.get_model("commons", "DataSource").objects.filter(code="ecocompteur").update(
        absolute_counts=True
    )


class Migration(migrations.Migration):
    dependencies = [("commons", "0007_merge_external_layers_import_status")]

    operations = [
        migrations.AddField(
            model_name="datasource",
            name="absolute_counts",
            field=models.BooleanField(
                default=False,
                help_text="Counts every passage (e.g. an eco-counter), not only a sample of users.",
            ),
        ),
        migrations.RunPython(set_absolute, migrations.RunPython.noop),
    ]
