"""Status and message of an import, recorded by the Celery worker. The imports
made before were run in the request: they are done."""

from django.db import migrations, models

STATUS_CHOICES = [("pending", "Pending"), ("done", "Done"), ("failed", "Failed")]


class Migration(migrations.Migration):
    dependencies = [
        ("commons", "0005_formats_and_domains_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataimport",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, default="done", max_length=10),
        ),
        migrations.AlterField(
            model_name="dataimport",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, default="pending", max_length=10),
        ),
        migrations.AddField(
            model_name="dataimport",
            name="message",
            field=models.TextField(blank=True),
        ),
    ]
