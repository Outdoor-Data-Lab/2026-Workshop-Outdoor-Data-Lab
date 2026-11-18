from django.contrib import admin, messages
from django.contrib.gis.forms import OSMWidget
from django.http import HttpResponseRedirect
from django.urls import reverse

from commons.models import PARSERS, DataSource

from .models import Offer, OfferImport
from .parsers import OfferParser


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

    A source provides either offers or counts: the traffic sources, those with a
    parser in commons.PARSERS, are left out.
    """

    list_display = ("source", "date_import", "file", "line_numbers", "error_numbers")
    list_filter = ("source",)
    fields = ("source", "file")

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(source__code__in=PARSERS)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "source":
            kwargs["queryset"] = DataSource.objects.exclude(code__in=PARSERS)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            count = OfferParser(obj).import_data()
        except ValueError as exc:
            obj.import_error = exc  # reported by response_add
        else:
            self.message_user(request, f"{count} offres importées, {obj.error_numbers} lignes en erreur.")

    def response_add(self, request, obj, post_url_continue=None):
        if not hasattr(obj, "import_error"):
            return super().response_add(request, obj, post_url_continue)
        # Rejected file: the reason instead of the success message.
        self.message_user(request, f"Import refusé : {obj.import_error}", messages.ERROR)
        return HttpResponseRedirect(reverse("admin:outdoor_offerimport_changelist"))
