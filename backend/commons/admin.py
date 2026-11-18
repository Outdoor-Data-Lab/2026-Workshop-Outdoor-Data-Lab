from django import forms
from django.contrib import admin, messages

from .models import PARSERS, DataImport, DataSource, Practice


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


class DataImportForm(forms.ModelForm):
    class Meta:
        model = DataImport
        fields = "__all__"

    def clean_source(self):
        source = self.cleaned_data["source"]
        if not self.instance.pk and source.code not in PARSERS:
            raise forms.ValidationError(
                f"Aucun parser n'est disponible pour la source « {source} »."
            )
        return source


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    form = DataImportForm
    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = ("source",)
    readonly_fields = ("date_import",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            return
        count = obj.run_parser()
        self.message_user(request, f"{count} éléments importés.", messages.SUCCESS)
