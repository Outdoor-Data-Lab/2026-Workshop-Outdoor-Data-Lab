from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0005_formats_and_domains_values"),
        ("traffic", "0005_data_import"),
    ]

    operations = [
        # RemoveIndex would run an unqualified DROP INDEX IF EXISTS, which finds
        # nothing outside the public schema: the index is dropped in SQL.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='DROP INDEX "traffic"."counting_measure_object_start"',
                    reverse_sql=(
                        'CREATE INDEX "counting_measure_object_start" '
                        'ON "traffic"."counting_measures" ("counting_object_id", "start_datetime")'
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="countingmeasure",
                    name="counting_measure_object_start",
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="countingmeasure",
            constraint=models.UniqueConstraint(
                fields=("counting_object", "start_datetime", "end_datetime", "practice", "unit"),
                name="counting_measure_unique_key",
                nulls_distinct=False,
            ),
        ),
    ]
