from django.contrib import admin

from .models import DataImport, DataSource, Practice


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "parent")
    list_filter = ("parent",)
    list_select_related = ("parent",)
    search_fields = ("code", "label")


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = ("source",)
    readonly_fields = ("date_import",)

    class Media:
        js = ("commons/import_loading.js",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            obj.run_parser()
