from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Activity, CountingMeasure, CountingObject, CountingObjectType, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("code_unit", "unit")
    search_fields = ("code_unit", "unit")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("code_activity", "activity")
    search_fields = ("code_activity", "activity")


@admin.register(CountingObjectType)
class CountingObjectTypeAdmin(admin.ModelAdmin):
    list_display = ("code_type", "type")
    search_fields = ("code_type", "type")


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
    list_display = ("counting_object", "start_datetime", "end_datetime", "count", "unit", "activity", "processed")
    list_filter = ("unit", "activity", "processed")
    list_select_related = ("counting_object", "unit", "activity")
    autocomplete_fields = ("counting_object",)
    readonly_fields = ("date_create", "date_update")
    date_hierarchy = "start_datetime"

