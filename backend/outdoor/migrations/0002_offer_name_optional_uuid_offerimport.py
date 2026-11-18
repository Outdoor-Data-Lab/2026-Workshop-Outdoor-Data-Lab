from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0002_initial_values"),
        ("outdoor", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="offer",
            name="name",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="offer",
            name="uuid",
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
        migrations.CreateModel(
            name="OfferImport",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("commons.dataimport",),
        ),
    ]
