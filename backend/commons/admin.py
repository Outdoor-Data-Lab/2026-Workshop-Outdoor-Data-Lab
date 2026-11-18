import json

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.module_loading import import_string

from .models import DataImport, DataSource, Practice


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
    """History of every import, whatever its domain. Files are imported from the
    page of their domain: traffic imports, observation imports, offer imports."""

    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = (("source", admin.RelatedOnlyFieldListFilter),)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ImportAdmin(admin.ModelAdmin):
    """Admin of the imports of one domain (a proxy of DataImport): only the sources
    of `parsers` are listed and offered, and the chosen file is imported on save.

    The parsers describe their file (CONTENT, EXAMPLE), shown under the source
    field; a file they refuse is reported on the form, and nothing is kept.
    """

    parsers: dict[str, str] = {}  # source code -> parser class path, of this domain
    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = (("source", admin.RelatedOnlyFieldListFilter),)
    readonly_fields = ("date_import",)

    class Media:
        js = ("commons/import_loading.js", "commons/import_example.js")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(source__code__in=self.parsers)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "source":
            kwargs["queryset"] = DataSource.objects.filter(code__in=self.parsers)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def render_change_form(self, request, context, *args, **kwargs):
        """Show what the file of the selected source holds, and an example, under the source field.

        Done when the form is displayed only: a POST that imports does not need it.
        """
        form = context["adminform"].form
        if "source" in form.fields:
            parsers = {
                source.pk: import_string(self.parsers[source.code])
                for source in DataSource.objects.filter(code__in=self.parsers)
            }
            examples = {
                pk: {"content": getattr(parser, "CONTENT", ""), "example": getattr(parser, "EXAMPLE", "")}
                for pk, parser in parsers.items()
            }
            form.fields["source"].help_text = format_html(
                '<span id="import-example" data-examples="{}"></span>', json.dumps(examples)
            )
        return super().render_change_form(request, context, *args, **kwargs)

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
        if change:
            return
        try:
            count = obj.run_parser()
        except ValueError as error:
            obj.file.delete(save=False)  # the rollback does not remove the stored file
            raise ImportRefused(error) from error
        self.message_user(request, f"{count} éléments importés.", messages.SUCCESS)
