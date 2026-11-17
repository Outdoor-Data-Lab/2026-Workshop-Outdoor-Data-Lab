"""App "ref_geo": read-only mapping of the PnX-Si/RefGeo schema ``ref_geo``.

The schema is loaded from ``data/ref_geo.dump`` (pg_restore), not created by
Django, so every model is ``managed = False``: migrations never create, alter
or drop these tables. Django has no schema option, hence the quoted
'ref_geo"."<table>' db_table trick (see the "traffic" app).

Not mapped: ``dem`` (raster), ``dem_vector`` and the ``cor_areas`` /
``cor_linear_area`` tables (no primary key).
Native geometries are in Lambert-93 (EPSG:2154); ``l_areas.geom_4326`` is the
WGS84 copy used for web output.
"""

from django.contrib.gis.db import models

DB_SCHEMA = "ref_geo"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


class _BibType(models.Model):
    id_type = models.AutoField(primary_key=True)
    type_name = models.CharField(max_length=200)
    type_code = models.CharField(max_length=25, unique=True)
    type_desc = models.TextField(null=True, blank=True)
    ref_name = models.CharField(max_length=200, null=True, blank=True)
    ref_version = models.IntegerField(null=True, blank=True)
    num_version = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        abstract = True
        managed = False

    def __str__(self):
        return self.type_name


class BibAreasType(_BibType):
    size_hierarchy = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("bib_areas_types")


class BibLinearsType(_BibType):
    meta_create_date = models.DateTimeField(null=True, blank=True)
    meta_update_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("bib_linears_types")


class BibPointsType(_BibType):
    meta_create_date = models.DateTimeField(null=True, blank=True)
    meta_update_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("bib_points_types")


class LArea(models.Model):
    id_area = models.AutoField(primary_key=True)
    type = models.ForeignKey(
        BibAreasType, models.DO_NOTHING, db_column="id_type", related_name="areas"
    )
    area_name = models.CharField(max_length=250, null=True, blank=True)
    area_code = models.CharField(max_length=25, null=True, blank=True)
    geom = models.MultiPolygonField(srid=2154, null=True, blank=True)
    centroid = models.PointField(srid=2154, null=True, blank=True)
    source = models.CharField(max_length=250, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    enable = models.BooleanField(default=True)
    additional_data = models.JSONField(null=True, blank=True)
    meta_create_date = models.DateTimeField(null=True, blank=True)
    meta_update_date = models.DateTimeField(null=True, blank=True)
    geom_4326 = models.MultiPolygonField(srid=4326, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("l_areas")

    def __str__(self):
        return self.area_name or self.area_code or str(self.pk)


class LLinear(models.Model):
    id_linear = models.AutoField(primary_key=True)
    type = models.ForeignKey(
        BibLinearsType, models.DO_NOTHING, db_column="id_type", related_name="linears"
    )
    linear_name = models.CharField(max_length=250)
    linear_code = models.CharField(max_length=25)
    enable = models.BooleanField(default=True)
    geom = models.GeometryField(srid=2154, null=True, blank=True)
    geojson_4326 = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=250, null=True, blank=True)
    additional_data = models.JSONField(null=True, blank=True)
    meta_create_date = models.DateTimeField(null=True, blank=True)
    meta_update_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("l_linears")

    def __str__(self):
        return self.linear_name


class LPoint(models.Model):
    id_point = models.AutoField(primary_key=True)
    type = models.ForeignKey(
        BibPointsType, models.DO_NOTHING, db_column="id_type", related_name="points"
    )
    point_name = models.CharField(max_length=250)
    point_code = models.CharField(max_length=25)
    enable = models.BooleanField(default=True)
    geom = models.GeometryField(srid=2154, null=True, blank=True)
    geojson_4326 = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=250, null=True, blank=True)
    additional_data = models.JSONField(null=True, blank=True)
    meta_create_date = models.DateTimeField(null=True, blank=True)
    meta_update_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("l_points")

    def __str__(self):
        return self.point_name


class LiMunicipality(models.Model):
    """Municipality attributes attached to an area of type COM."""

    id_municipality = models.CharField(max_length=25, primary_key=True)
    area = models.ForeignKey(
        LArea, models.DO_NOTHING, db_column="id_area", related_name="municipalities"
    )
    status = models.CharField(max_length=50, null=True, blank=True)
    insee_com = models.CharField(max_length=5, null=True, blank=True)
    nom_com = models.CharField(max_length=50, null=True, blank=True)
    insee_arr = models.CharField(max_length=2, null=True, blank=True)
    nom_dep = models.CharField(max_length=30, null=True, blank=True)
    insee_dep = models.CharField(max_length=3, null=True, blank=True)
    nom_reg = models.CharField(max_length=35, null=True, blank=True)
    insee_reg = models.CharField(max_length=2, null=True, blank=True)
    code_epci = models.CharField(max_length=9, null=True, blank=True)
    plani_precision = models.FloatField(null=True, blank=True)
    siren_code = models.CharField(max_length=10, null=True, blank=True)
    canton = models.CharField(max_length=200, null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    multican = models.CharField(max_length=3, null=True, blank=True)
    cc_nom = models.CharField(max_length=250, null=True, blank=True)
    cc_siren = models.BigIntegerField(null=True, blank=True)
    cc_nature = models.CharField(max_length=5, null=True, blank=True)
    cc_date_creation = models.CharField(max_length=10, null=True, blank=True)
    cc_date_effet = models.CharField(max_length=10, null=True, blank=True)
    insee_commune_nouvelle = models.CharField(max_length=5, null=True, blank=True)
    meta_create_date = models.DateTimeField(null=True, blank=True)
    meta_update_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("li_municipalities")

    def __str__(self):
        return self.nom_com or self.id_municipality


class LiGrid(models.Model):
    """Grid cell (e.g. 1x1 km) attached to an area of type grid."""

    id_grid = models.CharField(max_length=50, primary_key=True)
    area = models.ForeignKey(
        LArea, models.DO_NOTHING, db_column="id_area", related_name="grids"
    )
    cxmin = models.IntegerField(null=True, blank=True)
    cxmax = models.IntegerField(null=True, blank=True)
    cymin = models.IntegerField(null=True, blank=True)
    cymax = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = table("li_grids")

    def __str__(self):
        return self.id_grid


class TLinearGroup(models.Model):
    id_group = models.AutoField(primary_key=True)
    name = models.CharField(max_length=250)
    code = models.CharField(max_length=25, unique=True)
    linears = models.ManyToManyField(
        LLinear, through="CorLinearGroup", related_name="groups"
    )

    class Meta:
        managed = False
        db_table = table("t_linear_groups")

    def __str__(self):
        return self.name


class CorLinearGroup(models.Model):
    pk = models.CompositePrimaryKey("group_id", "linear_id")
    group = models.ForeignKey(TLinearGroup, models.DO_NOTHING, db_column="id_group")
    linear = models.ForeignKey(LLinear, models.DO_NOTHING, db_column="id_linear")

    class Meta:
        managed = False
        db_table = table("cor_linear_group")
