from django.contrib import admin, messages
from django.contrib.gis.forms import OSMWidget
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from commons.models import PARSERS, DataSource

from .models import Offer, OfferImport
from .parsers import OfferParser, describe_errors

PREVIEW_ERRORS = 20  # lines in error listed on the preview page
TOKEN_SALT = "outdoor.offerimport"
TOKEN_MAX_AGE = 24 * 3600  # seconds a preview can be applied


class ReadOnlyMapWidget(OSMWidget):
    """The admin map widget, to view a geometry: no "Delete all Features" link,
    and no drawing nor vertex editing (static/outdoor/read_only_map.js)."""

    class Media:
        # OLMapWidget.js repeated so that the media merge keeps it before ours.
        js = ("gis/js/OLMapWidget.js", "outdoor/read_only_map.js")

    def __init__(self):
        super().__init__(attrs={"read_only": True})

    def get_context(self, name, value, attrs):
        return super().get_context(name, value, attrs) | {"disabled": True}


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "practice", "source", "external_id", "date_update")
    list_filter = ("practice__parent", "practice", "source")
    list_select_related = ("practice", "source")
    search_fields = ("name", "external_id")
    # The view page is read-only, where the admin shows geom as WKT: a map instead.
    exclude = ("geom",)
    readonly_fields = ("map",)

    @property
    def media(self):
        return super().media + ReadOnlyMapWidget().media

    @admin.display(description="Geom")
    def map(self, obj):
        return ReadOnlyMapWidget().render("geom", obj.geom, attrs={"id": "id_geom"})

    # Offers come from imports: the admin only displays them.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OfferImport)
class OfferImportAdmin(admin.ModelAdmin):
    """Import a GeoPackage of offers for a source (see parsers.OfferParser).

    Two steps: the uploaded file is stored and previewed (offers created,
    updated, deleted, lines in error); the import is only created and applied
    once confirmed. A source provides either offers or counts: the traffic
    sources, those with a parser in commons.PARSERS, are left out.
    """

    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers", "offer_count")
    list_filter = ("source",)
    fields = ("source", "file")

    class Media:
        js = ("commons/import_loading.js",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .exclude(source__code__in=PARSERS)
            .annotate(offer_count=Count("offers"))
        )

    # Offers whose last import is this one: those its deletion would delete.
    @admin.display(description="Offers", ordering="offer_count")
    def offer_count(self, obj):
        return obj.offer_count

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["file"].help_text = format_html(
            "GeoPackage (.gpkg) with a single layer and a coordinate reference system. "
            "Columns: <code>id</code> (the offer's id in its source), <code>name</code>, "
            '<code>practice</code> (a <a href="{}">practice code</a>), <code>uuid</code> '
            "(optional). Geometry: points, lines, polygons or collections. Other columns are ignored.",
            reverse("admin:commons_practice_changelist"),
        )
        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "source":
            kwargs["queryset"] = DataSource.objects.exclude(code__in=PARSERS)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        return False

    def add_view(self, request, form_url="", extra_context=None):
        if request.method == "POST":
            if not self.has_add_permission(request):
                raise PermissionDenied
            if "token" in request.POST:
                return self.confirm(request)
            form = self.get_form(request)(request.POST, request.FILES)
            if form.is_valid():
                return self.preview(request, form.save(commit=False))
        return super().add_view(request, form_url, extra_context)

    def preview(self, request, data_import):
        """Store the file and show what the import would do, with Apply and Cancel."""
        upload = request.FILES["file"]
        data_import.file.save(upload.name, upload, save=False)
        parser = OfferParser(data_import)
        try:
            preview = parser.preview()
        except ValueError as exc:
            # Rejected file: kept as an import with one error, like the traffic imports.
            data_import.error_numbers = 1
            data_import.save()
            self.log_addition(request, data_import, [{"added": {}}])
            return self.done(request, f"Import rejected: {exc}", messages.ERROR)
        pending = {"source": data_import.source_id, "file": data_import.file.name}
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": "Offer import preview",
            "media": self.media,
            "data_import": data_import,
            "file_name": upload.name,
            "preview": preview,
            "errors": parser.errors[:PREVIEW_ERRORS],
            "more_errors": len(parser.errors) - PREVIEW_ERRORS,
            "token": signing.dumps(pending, salt=TOKEN_SALT),
        }
        return TemplateResponse(request, "admin/outdoor/offerimport/preview.html", context)

    def confirm(self, request):
        """Apply or cancel a previewed import."""
        try:
            pending = signing.loads(request.POST["token"], salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        except signing.BadSignature:
            return self.done(request, "Preview expired or invalid: start the import again.", messages.ERROR)
        # Test _cancel, not _apply: import_loading.js disables the buttons on submit,
        # so the Apply button's name is not sent.
        if "_cancel" in request.POST:
            OfferImport._meta.get_field("file").storage.delete(pending["file"])
            return self.done(request, "Import cancelled.", messages.INFO)

        data_import = OfferImport.objects.create(source_id=pending["source"], file=pending["file"])
        self.log_addition(request, data_import, [{"added": {}}])
        parser = OfferParser(data_import)
        try:
            count = parser.import_data()
        except ValueError as exc:
            return self.done(request, f"Import rejected: {exc}", messages.ERROR)
        message = f"{count} offer(s) imported, {len(parser.errors)} line(s) in error"
        if parser.errors:
            message += f": {describe_errors(parser.errors)}"
        return self.done(request, f"{message}.", messages.WARNING if parser.errors else messages.SUCCESS)

    def done(self, request, message, level):
        self.message_user(request, message, level)
        return HttpResponseRedirect(reverse("admin:outdoor_offerimport_changelist"))
