import json

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.module_loading import import_string

from .models import PARSERS, DataImport, DataSource, Practice


class ImportRefused(Exception):
    """The parser refused the file: shown to the user instead of a server error."""


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
        js = ("commons/import_loading.js", "commons/import_example.js")

    def get_form(self, request, obj=None, **kwargs):
        """Show the expected file of the selected source under the source field."""
        form = super().get_form(request, obj, **kwargs)
        examples = {
            source.pk: import_string(PARSERS[source.code]).EXAMPLE
            for source in DataSource.objects.filter(code__in=PARSERS)
        }
        form.base_fields["source"].help_text = format_html(
            '<span id="import-example" data-examples="{}"></span>', json.dumps(examples)
        )
        return form

    def add_view(self, request, form_url="", extra_context=None):
        # The admin saves within a transaction: an ImportRefused leaving it rolls
        # back the DataImport and its log entry, so nothing is left of the import.
        try:
            return super().add_view(request, form_url, extra_context)
        except ImportRefused as error:
            self.message_user(request, f"Import refusé, rien n'a été enregistré : {error}", messages.ERROR)
            # Back to the empty form, with the same source selected.
            return HttpResponseRedirect(f"{request.path}?{urlencode({'source': request.POST.get('source', '')})}")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            try:
                obj.run_parser()
            except ValueError as error:
                obj.file.delete(save=False)  # the rollback does not remove the stored file
                raise ImportRefused(error) from error
