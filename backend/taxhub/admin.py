from django.contrib import admin
from django.db.models import F

from .models import Taxref, VBdcStatutAdminView


class ReadOnlyAdmin(admin.ModelAdmin):
    """Admin interface limited to viewing existing database rows."""

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Taxref)
class TaxrefAdmin(ReadOnlyAdmin):
    list_display = (
        "cd_nom",
        "nom_valide",
        "nom_vern",
        "id_rang",
        "famille",
        "group2_inpn",
    )
    list_filter = ("id_rang", "regne", "group1_inpn", "group2_inpn")
    search_fields = (
        "=cd_nom",
        "=cd_ref",
        "lb_nom",
        "nom_complet",
        "nom_valide",
        "nom_vern",
    )
    ordering = ("cd_nom",)
    list_per_page = 100
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(cd_nom=F("cd_ref"))


@admin.register(VBdcStatutAdminView)
class VBdcStatusAdmin(ReadOnlyAdmin):
    # The source view has a composite key, unsupported by Django admin.
    # Keep the changelist read-only and do not generate ambiguous detail URLs.
    list_display_links = None
    list_display = (
        "cd_nom",
        "cd_ref",
        "code_statut",
        "label_statut",
        "lb_type_statut",
        "thematique",
    )
    list_filter = ("cd_type_statut", "thematique", "regroupement_type")
    search_fields = (
        "=cd_nom",
        "=cd_ref",
        "code_statut",
        "label_statut",
        "lb_type_statut",
        "full_citation",
    )
    ordering = ("cd_nom", "lb_type_statut", "code_statut")
    list_per_page = 100
    show_full_result_count = False
