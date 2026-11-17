from django.contrib import admin

from .models import DataImport, DataSource


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("code_source", "source")
    search_fields = ("code_source", "source")


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("source", "date_import", "line_numbers", "error_numbers")
    list_filter = ("source",)
    readonly_fields = ("date_import",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            obj.run_parser()
