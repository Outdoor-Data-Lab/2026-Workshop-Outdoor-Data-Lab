import json

from django import forms
from django.contrib import admin, messages
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.module_loading import import_string

from .models import DOMAINS, DataImport, DataSource, ExternalLayer, Practice
from .parsers import describe_errors

PREVIEW_ERRORS = 20  # lines in error listed on the preview page
TOKEN_MAX_AGE = 24 * 3600  # seconds a preview can be applied


class DataSourceForm(forms.ModelForm):
    domains = forms.MultipleChoiceField(
        choices=DOMAINS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=DataSource._meta.get_field("domains").help_text,
    )

    class Meta:
        model = DataSource
        fields = "__all__"


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    form = DataSourceForm
    list_display = ("code", "label", "domains")
    search_fields = ("code", "label")


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "parent")
    list_filter = ("parent",)
    list_select_related = ("parent",)
    search_fields = ("code", "label")


@admin.register(ExternalLayer)
class ExternalLayerAdmin(admin.ModelAdmin):
    list_display = ("label", "url")
    search_fields = ("label", "url")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "color":
            kwargs["widget"] = forms.TextInput(attrs={"type": "color"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    """History of every import, whatever its domain. Files are imported from the
    page of their domain: traffic imports, observation imports, offer imports."""

    list_display = ("source", "format", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = ("format", ("source", admin.RelatedOnlyFieldListFilter))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ImportAdmin(admin.ModelAdmin):
    """Admin of the imports of one domain (a proxy of DataImport, in the domain app).

    The user chooses the format of the file (which parser reads it, among
    `parsers`) and its source (among the sources whose `domains` include this
    app). The uploaded file is imported at once. With `with_preview`, it is first
    previewed (lines read, changes, lines in error) and only applied once
    confirmed, "Cancel" deleting it: the file is then read twice. A file the
    parser refuses keeps nothing: the form comes back with the reason, the same
    format and the same source.
    """

    parsers: dict[str, str] = {}  # format code -> parser class path, of this domain
    with_preview = False
    list_display = ("source", "format", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = ("format", ("source", admin.RelatedOnlyFieldListFilter))
    fields = ("format", "source", "file")

    class Media:
        js = ("commons/import_loading.js", "commons/import_example.js")

    def get_parser(self, format_code):
        """The parser class of a format."""
        return import_string(self.parsers[format_code])

    def get_sources(self):
        """The sources offered on this page: those of this domain."""
        return DataSource.objects.filter(domains__contains=[self.opts.app_label])

    def get_queryset(self, request):
        return super().get_queryset(request).filter(format__in=self.parsers)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "format":
            choices = [(code, self.get_parser(code).LABEL) for code in self.parsers]
            # A single format is preselected; with several, the user must choose.
            initial = choices[0][0] if len(choices) == 1 else None
            if initial is None:
                choices.insert(0, ("", "---------"))
            return forms.ChoiceField(choices=choices, initial=initial, help_text="How the file is read.")
        if db_field.name == "source":
            kwargs["queryset"] = self.get_sources()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        # An import is applied once, then only viewed.
        return False

    def render_change_form(self, request, context, *args, **kwargs):
        """Show what a file of the selected format holds, and an example, under the format field.

        Done when the form is displayed only: a POST that imports does not need it.
        """
        form = context["adminform"].form
        if "format" in form.fields:
            examples = {
                code: {"content": parser.CONTENT, "example": parser.EXAMPLE}
                for code in self.parsers
                for parser in [self.get_parser(code)]
            }
            form.fields["format"].help_text = format_html(
                '<span id="import-example" data-examples="{}" data-preview="{}"></span>',
                json.dumps(examples),
                "1" if self.with_preview else "",
            )
        return super().render_change_form(request, context, *args, **kwargs)

    def add_view(self, request, form_url="", extra_context=None):
        if request.method == "POST":
            if not self.has_add_permission(request):
                raise PermissionDenied
            if "token" in request.POST:
                return self.confirm(request)
            form = self.get_form(request)(request.POST, request.FILES)
            if form.is_valid():
                data_import = form.save(commit=False)
                upload = request.FILES["file"]
                data_import.file.save(upload.name, upload, save=False)
                if self.with_preview:
                    return self.show_preview(request, data_import, upload.name)
                return self.apply(request, data_import.format, data_import.source, data_import.file.name)
        return super().add_view(request, form_url, extra_context)

    def show_preview(self, request, data_import, file_name):
        """Show what the import of the stored file would do, with Apply and Cancel."""
        parser = self.get_parser(data_import.format)(data_import)
        try:
            preview = parser.preview()
        except ValueError as error:
            data_import.file.delete(save=False)
            return self.refused(request, error, data_import.format, data_import.source_id)
        pending = {"format": data_import.format, "source": data_import.source_id, "file": data_import.file.name}
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": f"Preview of the {self.opts.verbose_name}",
            "media": self.media,
            "format": parser.LABEL,
            "source": data_import.source,
            "file_name": file_name,
            "preview": preview,
            "errors": parser.errors[:PREVIEW_ERRORS],
            "more_errors": len(parser.errors) - PREVIEW_ERRORS,
            "token": signing.dumps(pending, salt=self.opts.label_lower),
        }
        return TemplateResponse(request, "admin/commons/import_preview.html", context)

    def confirm(self, request):
        """Apply or cancel a previewed import."""
        try:
            pending = signing.loads(request.POST["token"], salt=self.opts.label_lower, max_age=TOKEN_MAX_AGE)
        except signing.BadSignature:
            return self.done(request, "Preview expired or invalid: start the import again.", messages.ERROR)
        # Test _cancel, not _apply: import_loading.js disables the buttons on submit,
        # so the Apply button's name is not sent.
        if "_cancel" in request.POST:
            DataImport._meta.get_field("file").storage.delete(pending["file"])
            return self.done(request, "Import cancelled.", messages.INFO)
        source = DataSource.objects.get(pk=pending["source"])
        return self.apply(request, pending["format"], source, pending["file"])

    def apply(self, request, format_code, source, file_name):
        """Import the stored file; a refused file keeps nothing."""
        try:
            with transaction.atomic():
                data_import = self.model.objects.create(format=format_code, source=source, file=file_name)
                parser = self.get_parser(format_code)(data_import)
                count = parser.import_data()
                self.log_addition(request, data_import, [{"added": {}}])
        except ValueError as error:
            DataImport._meta.get_field("file").storage.delete(file_name)
            return self.refused(request, error, format_code, source.pk)
        message = f"{count} item(s) imported, {data_import.error_numbers} line(s) in error"
        if parser.errors:
            message += f": {describe_errors(parser.errors)}"
        return self.done(request, f"{message}.", messages.WARNING if data_import.error_numbers else messages.SUCCESS)

    def refused(self, request, error, format_code, source_id):
        """Back to the empty form, with the same format, source and the reason: nothing is kept."""
        self.message_user(request, f"Import refused, nothing was saved: {error}", messages.ERROR)
        url = reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_add")
        return HttpResponseRedirect(f"{url}?{urlencode({'format': format_code, 'source': source_id})}")

    def done(self, request, message, level):
        self.message_user(request, message, level)
        return HttpResponseRedirect(reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"))
