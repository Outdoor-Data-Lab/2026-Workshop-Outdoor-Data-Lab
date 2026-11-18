from django.db import models


class MaterializedViewCount(models.Model):
    pk = models.CompositePrimaryKey("id_area", "id_source", "year", "month")
    id_area = models.IntegerField()
    id_source = models.IntegerField()
    year = models.IntegerField()
    month = models.IntegerField()
    counts = models.IntegerField()
    count_segment = models.IntegerField()
    count_presence = models.IntegerField()

    class Meta:
        managed = False  # This tells Django not to manage this table
        app_label = "traffic"
        db_table = 'traffic"."materialized_view_counts'
