from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import (
    BibAreasType,
    BibLinearsType,
    BibPointsType,
    LArea,
    LiMunicipality,
    LLinear,
    LPoint,
    TLinearGroup,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """The data comes from the RefGeo dump: browse only."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BibAreasType, BibLinearsType, BibPointsType)
class BibTypeAdmin(ReadOnlyAdmin):
    list_display = ("type_code", "type_name", "ref_name", "ref_version")
    search_fields = ("type_code", "type_name")


@admin.register(LArea)
class LAreaAdmin(ReadOnlyAdmin, GISModelAdmin):
    list_display = ("area_code", "area_name", "type", "enable")
    list_filter = ("type",)
    search_fields = ("area_code", "area_name")
    list_select_related = ("type",)
    # geom columns are heavy: keep them out of the detail page
    exclude = ("geom", "geom_4326", "centroid")


@admin.register(LLinear)
class LLinearAdmin(ReadOnlyAdmin):
    list_display = ("linear_code", "linear_name", "type")
    search_fields = ("linear_code", "linear_name")
    exclude = ("geom", "geojson_4326")


@admin.register(LPoint)
class LPointAdmin(ReadOnlyAdmin):
    list_display = ("point_code", "point_name", "type")
    search_fields = ("point_code", "point_name")
    exclude = ("geom", "geojson_4326")


@admin.register(LiMunicipality)
class LiMunicipalityAdmin(ReadOnlyAdmin):
    list_display = ("insee_com", "nom_com", "nom_dep", "population")
    search_fields = ("insee_com", "nom_com")


@admin.register(TLinearGroup)
class TLinearGroupAdmin(ReadOnlyAdmin):
    list_display = ("code", "name")
