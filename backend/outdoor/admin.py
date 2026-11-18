from django.contrib import admin
from django.contrib.gis.forms import OSMWidget
from django.db.models import Count

from commons.admin import ImportAdmin
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
class OfferImportAdmin(ImportAdmin):
    """Import a GeoPackage of offers (see parsers.OfferParser): one parser for every
    source, any source but those of the other domains (commons.PARSERS)."""

    list_display = (*ImportAdmin.list_display, "offer_count")
    # The file is the reference for its source: preview the offers it would delete.
    with_preview = True

    def get_sources(self):
        return DataSource.objects.exclude(code__in=PARSERS)

    def get_parser(self, source):
        return OfferParser

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(offer_count=Count("offers"))

    # Offers whose last import is this one: those its deletion would delete.
    @admin.display(description="Offers", ordering="offer_count")
    def offer_count(self, obj):
        return obj.offer_count
