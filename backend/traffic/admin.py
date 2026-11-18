from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from commons.admin import ImportAdmin

from .models import CountingMeasure, CountingObject, CountingObjectType, TrafficImport, Unit
from .parsers import PARSERS


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(CountingObjectType)
class CountingObjectTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(CountingObject)
class CountingObjectAdmin(GISModelAdmin):
    list_display = ("__str__", "type", "source", "manager", "installation_date", "processed")
    list_filter = ("type", "source", "processed")
    list_select_related = ("type", "source")
    search_fields = ("external_id", "manager")
    readonly_fields = ("uuid", "date_create", "date_update", "first_data", "latest_data")

    def get_queryset(self, request):
        return super().get_queryset(request).with_data_range()

    @admin.display(description="Première donnée")
    def first_data(self, obj):
        return obj.first_data

    @admin.display(description="Dernière donnée")
    def latest_data(self, obj):
        return obj.latest_data


@admin.register(CountingMeasure)
class CountingMeasureAdmin(admin.ModelAdmin):
    list_display = ("counting_object", "start_datetime", "end_datetime", "count", "unit", "practice", "processed")
    list_filter = ("unit", "practice", "processed")
    list_select_related = ("counting_object", "unit", "practice")
    date_hierarchy = "start_datetime"

    # Measures come from CSV imports: the admin only displays them.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TrafficImport)
class TrafficImportAdmin(ImportAdmin):
    parsers = PARSERS
