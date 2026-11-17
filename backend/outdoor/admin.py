from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Offer


@admin.register(Offer)
class OfferAdmin(GISModelAdmin):
    list_display = ("__str__", "practice", "source", "date_update")
    list_filter = ("practice__parent", "practice", "source")
    list_select_related = ("practice", "source")
    search_fields = ("external_id",)

    # Offers come from imports: the admin only displays them.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
