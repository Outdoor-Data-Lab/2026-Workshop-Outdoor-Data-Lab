from django.contrib import admin

from .models import DataImport, DataSource, PracticeCategory


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(PracticeCategory)
class PracticeCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = ("source",)
    readonly_fields = ("date_import",)
