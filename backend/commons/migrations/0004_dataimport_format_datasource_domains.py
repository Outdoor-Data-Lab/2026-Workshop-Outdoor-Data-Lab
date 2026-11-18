import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0003_rename_inpn_source_sinp"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasource",
            name="domains",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[("traffic", "Traffic"), ("biodiversity", "Biodiversity"), ("outdoor", "Outdoor")],
                    max_length=20,
                ),
                blank=True,
                default=list,
                help_text="Import pages offering this source; none for a source used only as an origin.",
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="dataimport",
            name="format",
            field=models.CharField(default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="dataimport",
            name="source",
            field=models.ForeignKey(
                help_text="Who provided the file.",
                on_delete=models.deletion.PROTECT,
                related_name="imports",
                to="commons.datasource",
            ),
        ),
    ]
