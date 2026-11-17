from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commons", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataimport",
            name="file",
            field=models.FileField(default="", upload_to="imports"),
            preserve_default=False,
        ),
    ]
