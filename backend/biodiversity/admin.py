from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import HabitatRecord, HabitatStation, TaxonomicReferential, TaxonRecord


@admin.register(TaxonomicReferential)
class TaxonomicReferentialAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(TaxonRecord)
class TaxonRecordAdmin(GISModelAdmin):
    list_display = (
        "scientific_name",
        "cd_ref",
        "record_start_date",
        "record_end_date",
        "source",
    )
    list_filter = ("source", "referential")
    list_select_related = ("source",)
    search_fields = ("scientific_name", "original_id_taxon", "=cd_ref", "=uuid")
    date_hierarchy = "record_start_date"
    readonly_fields = ("uuid",)


class HabitatRecordInline(admin.TabularInline):
    model = HabitatRecord
    extra = 0
    readonly_fields = ("uuid",)


@admin.register(HabitatStation)
class HabitatStationAdmin(GISModelAdmin):
    list_display = ("__str__", "source")
    list_filter = ("source",)
    list_select_related = ("source",)
    search_fields = ("=uuid",)
    readonly_fields = ("uuid",)
    inlines = [HabitatRecordInline]


@admin.register(HabitatRecord)
class HabitatRecordAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cd_hab", "community_interest")
    list_filter = ("community_interest",)
    list_select_related = ("station",)
    search_fields = ("=cd_hab", "=uuid")
    readonly_fields = ("uuid",)
