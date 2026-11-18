"""Read-only Django models for the TaxHub ``taxonomie`` schema."""

from urllib.parse import urljoin

from django.conf import settings
from django.db import models

from ref_geo.models import LArea


DB_SCHEMA = "taxonomie"


def table(name: str) -> str:
    """Build a schema-qualified table name understood by Django."""

    return f'{DB_SCHEMA}"."{name}'


class UnmanagedTaxhubModel(models.Model):
    class Meta:
        abstract = True
        managed = False


# class VMRegne(UnmanagedTaxhubModel):
#     regne = models.CharField(primary_key=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("vm_regne")

#     def __str__(self) -> str:
#         return self.regne


# class VMGroup2Inpn(UnmanagedTaxhubModel):
#     group2_inpn = models.CharField(primary_key=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("vm_group2_inpn")

#     def __str__(self) -> str:
#         return self.group2_inpn


# class BibTaxrefHabitats(UnmanagedTaxhubModel):
#     id_habitat = models.IntegerField(primary_key=True)
#     nom_habitat = models.CharField(null=True, blank=True)
#     desc_habitat = models.TextField(null=True, blank=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("bib_taxref_habitats")

#     def __str__(self) -> str:
#         return self.nom_habitat or str(self.pk)


class BibTaxrefRangs(UnmanagedTaxhubModel):
    id_rang = models.CharField(primary_key=True)
    nom_rang = models.CharField(null=True, blank=True)
    tri_rang = models.IntegerField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bib_taxref_rangs")

    def __str__(self) -> str:
        return self.nom_rang or self.pk


# class BibTaxrefStatus(UnmanagedTaxhubModel):
#     id_statut = models.CharField(primary_key=True)
#     nom_statut = models.CharField(null=True, blank=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("bib_taxref_statuts")

#     def __str__(self) -> str:
#         return self.nom_statut or self.pk


# class BibThemes(UnmanagedTaxhubModel):
#     id_theme = models.IntegerField(primary_key=True)
#     nom_theme = models.CharField(null=True, blank=True)
#     desc_theme = models.CharField(null=True, blank=True)
#     ordre = models.IntegerField(null=True, blank=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("bib_themes")

#     def __str__(self) -> str:
#         return self.nom_theme or str(self.pk)


# class BibAttributs(UnmanagedTaxhubModel):
#     id_attribut = models.IntegerField(primary_key=True)
#     nom_attribut = models.CharField()
#     label_attribut = models.CharField()
#     liste_valeur_attribut = models.CharField(null=True, blank=True)
#     obligatoire = models.BooleanField(null=True, blank=True)
#     desc_attribut = models.TextField(null=True, blank=True)
#     type_attribut = models.CharField(null=True, blank=True)
#     type_widget = models.CharField()
#     regne = models.ForeignKey(
#         VMRegne,
#         models.DO_NOTHING,
#         db_column="regne",
#         related_name="attributs",
#         null=True,
#         blank=True,
#     )
#     group2_inpn = models.ForeignKey(
#         VMGroup2Inpn,
#         models.DO_NOTHING,
#         db_column="group2_inpn",
#         related_name="attributs",
#         null=True,
#         blank=True,
#     )
#     theme = models.ForeignKey(
#         BibThemes,
#         models.DO_NOTHING,
#         db_column="id_theme",
#         related_name="attributs",
#     )
#     ordre = models.IntegerField(null=True, blank=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("bib_attributs")

#     def __str__(self) -> str:
#         return self.label_attribut


# class BibTypesMedia(UnmanagedTaxhubModel):
#     id_type = models.IntegerField(primary_key=True)
#     nom_type_media = models.CharField(null=True, blank=True)
#     desc_type_media = models.TextField(null=True, blank=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("bib_types_media")

#     def __str__(self) -> str:
#         return self.nom_type_media or str(self.pk)


class Taxref(UnmanagedTaxhubModel):
    cd_nom = models.IntegerField(primary_key=True)
    id_statut = models.CharField(null=True, blank=True)
    id_habitat = models.IntegerField(null=True, blank=True)
    id_rang = models.CharField(null=True, blank=True)
    regne = models.CharField(null=True, blank=True)
    phylum = models.CharField(null=True, blank=True)
    classe = models.CharField(null=True, blank=True)
    ordre = models.CharField(null=True, blank=True)
    famille = models.CharField(null=True, blank=True)
    sous_famille = models.CharField(null=True, blank=True)
    tribu = models.CharField(null=True, blank=True)
    cd_taxsup = models.IntegerField(null=True, blank=True)
    cd_sup = models.IntegerField(null=True, blank=True)
    cd_ref = models.IntegerField(null=True, blank=True)
    cd_ba = models.IntegerField(null=True, blank=True)
    lb_nom = models.CharField(null=True, blank=True)
    lb_auteur = models.CharField(null=True, blank=True)
    nomenclatural_comment = models.CharField(null=True, blank=True)
    nom_complet = models.CharField(null=True, blank=True)
    nom_complet_html = models.CharField(null=True, blank=True)
    nom_vern = models.CharField(null=True, blank=True)
    nom_valide = models.CharField(null=True, blank=True)
    nom_vern_eng = models.CharField(null=True, blank=True)
    group1_inpn = models.CharField(null=True, blank=True)
    group2_inpn = models.CharField(null=True, blank=True)
    group3_inpn = models.CharField(null=True, blank=True)
    url = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("taxref")

    def __str__(self) -> str:
        return self.nom_complet or self.lb_nom or str(self.pk)

    @property
    def nom_vern_or_lb_nom(self) -> str | None:
        return self.nom_vern or self.lb_nom

    @property
    def synonymes(self):
        if self.cd_ref is None:
            return type(self).objects.none()
        return type(self).objects.filter(cd_ref=self.cd_ref)

    @property
    def parent(self):
        if self.cd_sup is None:
            return None
        return type(self).objects.filter(cd_ref=self.cd_sup).first()

    @property
    def rang(self):
        if self.id_rang is None:
            return None
        return BibTaxrefRangs.objects.filter(pk=self.id_rang).first()

    # @property
    # def habitat(self):
    #     if self.id_habitat is None:
    #         return None
    #     return BibTaxrefHabitats.objects.filter(pk=self.id_habitat).first()

    # @property
    # def statut_presence(self):
    #     if self.id_statut is None:
    #         return None
    #     return BibTaxrefStatus.objects.filter(pk=self.id_statut).first()

    @property
    def status(self):
        if self.cd_ref is None:
            return VBdcStatus.objects.none()
        return VBdcStatus.objects.filter(cd_nom=self.cd_ref).order_by("lb_type_statut")

    # @property
    # def nb_medias(self) -> int:
    #     if self.cd_ref is None:
    #         return 0
    #     return TMedias.objects.filter(taxon_id=self.cd_ref).count()

    # @property
    # def nb_attributs(self) -> int:
    #     if self.cd_ref is None:
    #         return 0
    #     return CorTaxonAttribut.objects.filter(taxon_id=self.cd_ref).count()

    def __le__(self, other) -> bool:
        return self.tree <= other.tree


# class CorTaxonAttribut(UnmanagedTaxhubModel):
#     pk = models.CompositePrimaryKey("attribut_id", "taxon_id")
#     attribut = models.ForeignKey(
#         BibAttributs,
#         models.DO_NOTHING,
#         db_column="id_attribut",
#         related_name="valeurs_taxons",
#     )
#     taxon = models.ForeignKey(
#         Taxref,
#         models.DO_NOTHING,
#         db_column="cd_ref",
#         related_name="attributs",
#     )
#     valeur_attribut = models.TextField()

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("cor_taxon_attribut")


# class BibListes(UnmanagedTaxhubModel):
#     id_liste = models.IntegerField(primary_key=True)
#     code_liste = models.CharField(null=True, blank=True)
#     nom_liste = models.CharField(null=True, blank=True)
#     desc_liste = models.TextField(null=True, blank=True)
#     regne = models.ForeignKey(
#         VMRegne,
#         models.DO_NOTHING,
#         db_column="regne",
#         related_name="listes",
#         null=True,
#         blank=True,
#     )
#     group2_inpn = models.ForeignKey(
#         VMGroup2Inpn,
#         models.DO_NOTHING,
#         db_column="group2_inpn",
#         related_name="listes",
#         null=True,
#         blank=True,
#     )
#     taxons = models.ManyToManyField(
#         Taxref,
#         through="CorNomListe",
#         related_name="listes",
#     )

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("bib_listes")

#     def __str__(self) -> str:
#         return self.nom_liste or self.code_liste or str(self.pk)

#     @property
#     def nb_taxons(self) -> int:
#         return self.taxons.count()


# class CorNomListe(UnmanagedTaxhubModel):
#     pk = models.CompositePrimaryKey("liste_id", "taxon_id")
#     liste = models.ForeignKey(
#         BibListes,
#         models.DO_NOTHING,
#         db_column="id_liste",
#         related_name="associations_taxons",
#     )
#     taxon = models.ForeignKey(
#         Taxref,
#         models.DO_NOTHING,
#         db_column="cd_nom",
#         related_name="associations_listes",
#     )

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("cor_nom_liste")


# class TMedias(UnmanagedTaxhubModel):
#     id_media = models.IntegerField(primary_key=True)
#     taxon = models.ForeignKey(
#         Taxref,
#         models.DO_NOTHING,
#         db_column="cd_ref",
#         related_name="medias",
#     )
#     titre = models.CharField()
#     url = models.CharField(null=True, blank=True)
#     chemin = models.CharField(null=True, blank=True)
#     auteur = models.CharField(null=True, blank=True)
#     desc_media = models.TextField(null=True, blank=True)
#     source = models.CharField(null=True, blank=True)
#     licence = models.CharField(null=True, blank=True)
#     is_public = models.BooleanField(default=True)
#     type_media = models.ForeignKey(
#         BibTypesMedia,
#         models.DO_NOTHING,
#         db_column="id_type",
#         related_name="medias",
#     )

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("t_medias")

#     def __str__(self) -> str:
#         return self.titre

#     @property
#     def media_url(self) -> str | None:
#         if self.url:
#             return self.url
#         if self.chemin:
#             base_url = settings.MEDIA_URL.rstrip("/") + "/"
#             return urljoin(base_url, f"taxhub/{self.chemin.lstrip('/')}")
#         return None


class VBdcStatus(UnmanagedTaxhubModel):
    """Read-only mapping of the ``v_bdc_status`` database view."""

    pk = models.CompositePrimaryKey(
        "cd_nom",
        "code_statut",
        "cd_type_statut",
        "cd_st_text",
        "full_citation",
    )
    cd_nom = models.IntegerField()
    cd_ref = models.IntegerField(null=True, blank=True)
    rq_statut = models.CharField(null=True, blank=True)
    code_statut = models.CharField()
    label_statut = models.CharField(null=True, blank=True)
    cd_type_statut = models.CharField()
    lb_type_statut = models.CharField(null=True, blank=True)
    regroupement_type = models.CharField(null=True, blank=True)
    thematique = models.CharField(null=True, blank=True)
    cd_st_text = models.CharField()
    cd_sig = models.CharField(null=True, blank=True)
    cd_doc = models.CharField(null=True, blank=True)
    niveau_admin = models.CharField(null=True, blank=True)
    cd_iso3166_1 = models.CharField(null=True, blank=True)
    cd_iso3166_2 = models.CharField(null=True, blank=True)
    full_citation = models.CharField()
    doc_url = models.CharField(null=True, blank=True)
    type_value = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("v_bdc_status")


class VBdcStatutAdminView(UnmanagedTaxhubModel):
    """Admin-only projection of ``v_bdc_status``.

    Django admin does not support composite primary keys. ``cd_nom`` is used
    only as the technical row identifier required by the changelist; the
    admin deliberately exposes no detail, edit or action URL for this model.
    """

    cd_nom = models.IntegerField(primary_key=True)
    cd_ref = models.IntegerField(null=True, blank=True)
    rq_statut = models.CharField(null=True, blank=True)
    code_statut = models.CharField()
    label_statut = models.CharField(null=True, blank=True)
    cd_type_statut = models.CharField()
    lb_type_statut = models.CharField(null=True, blank=True)
    regroupement_type = models.CharField(null=True, blank=True)
    thematique = models.CharField(null=True, blank=True)
    cd_st_text = models.CharField()
    cd_sig = models.CharField(null=True, blank=True)
    cd_doc = models.CharField(null=True, blank=True)
    niveau_admin = models.CharField(null=True, blank=True)
    cd_iso3166_1 = models.CharField(null=True, blank=True)
    cd_iso3166_2 = models.CharField(null=True, blank=True)
    full_citation = models.CharField()
    doc_url = models.CharField(null=True, blank=True)
    type_value = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("v_bdc_status")
        default_permissions = ("view",)
        verbose_name = "statut BDC"
        verbose_name_plural = "statuts BDC"


class VMTaxrefListForautocomplete(UnmanagedTaxhubModel):
    gid = models.IntegerField(primary_key=True)
    taxon = models.ForeignKey(
        Taxref,
        models.DO_NOTHING,
        db_column="cd_nom",
        related_name="autocomplete_entries",
        null=True,
        blank=True,
    )
    search_name = models.CharField(null=True, blank=True)
    unaccent_search_name = models.CharField(null=True, blank=True)
    cd_ref = models.IntegerField(null=True, blank=True)
    nom_valide = models.CharField(null=True, blank=True)
    lb_nom = models.CharField(null=True, blank=True)
    nom_vern = models.CharField(null=True, blank=True)
    regne = models.CharField(null=True, blank=True)
    group2_inpn = models.CharField(null=True, blank=True)
    group3_inpn = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("vm_taxref_list_forautocomplete")

    def __str__(self) -> str:
        return self.search_name or str(self.pk)


class VMTaxrefHierarchie(UnmanagedTaxhubModel):
    cd_nom = models.IntegerField(primary_key=True)
    cd_ref = models.IntegerField(null=True, blank=True)
    regne = models.CharField(null=True, blank=True)
    phylum = models.CharField(null=True, blank=True)
    classe = models.CharField(null=True, blank=True)
    ordre = models.CharField(null=True, blank=True)
    famille = models.CharField(null=True, blank=True)
    lb_nom = models.CharField(null=True, blank=True)
    id_rang = models.CharField(null=True, blank=True)
    nb_tx_fm = models.IntegerField(null=True, blank=True)
    nb_tx_or = models.IntegerField(null=True, blank=True)
    nb_tx_cl = models.IntegerField(null=True, blank=True)
    nb_tx_ph = models.IntegerField(null=True, blank=True)
    nb_tx_kd = models.IntegerField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("vm_taxref_hierarchie")

    def __str__(self) -> str:
        return self.lb_nom or str(self.pk)


class TaxrefBdcStatutType(UnmanagedTaxhubModel):
    cd_type_statut = models.CharField(primary_key=True)
    lb_type_statut = models.CharField(null=True, blank=True)
    regroupement_type = models.CharField(null=True, blank=True)
    thematique = models.CharField(null=True, blank=True)
    type_value = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bdc_statut_type")

    @property
    def display(self) -> str:
        return f"{self.lb_type_statut} - {self.cd_type_statut}"

    def __str__(self) -> str:
        return self.display


class TaxrefBdcStatutText(UnmanagedTaxhubModel):
    id_text = models.IntegerField(primary_key=True)
    cd_st_text = models.CharField(null=True, blank=True)
    type_statut = models.ForeignKey(
        TaxrefBdcStatutType,
        models.DO_NOTHING,
        db_column="cd_type_statut",
        related_name="textes",
    )
    cd_sig = models.CharField(null=True, blank=True)
    cd_doc = models.CharField(null=True, blank=True)
    niveau_admin = models.CharField(null=True, blank=True)
    cd_iso3166_1 = models.CharField(null=True, blank=True)
    cd_iso3166_2 = models.CharField(null=True, blank=True)
    lb_adm_tr = models.CharField(null=True, blank=True)
    full_citation = models.CharField(null=True, blank=True)
    doc_url = models.CharField(null=True, blank=True)
    enable = models.BooleanField(null=True, blank=True)
    areas = models.ManyToManyField(
        LArea,
        through="BdcStatutCorTextArea",
        related_name="textes_bdc_statut",
    )

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bdc_statut_text")

    def __str__(self) -> str:
        return self.full_citation or self.cd_st_text or str(self.pk)


class BdcStatutCorTextArea(UnmanagedTaxhubModel):
    pk = models.CompositePrimaryKey("text_id", "area_id")
    text = models.ForeignKey(
        TaxrefBdcStatutText,
        models.DO_NOTHING,
        db_column="id_text",
        related_name="associations_areas",
    )
    area = models.ForeignKey(
        LArea,
        models.DO_NOTHING,
        db_column="id_area",
        related_name="associations_textes_bdc_statut",
    )

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bdc_statut_cor_text_area")


class TaxrefBdcStatutValues(UnmanagedTaxhubModel):
    id_value = models.IntegerField(primary_key=True)
    code_statut = models.CharField(null=True, blank=True)
    label_statut = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bdc_statut_values")

    @property
    def display(self) -> str:
        return f"{self.code_statut} - {self.label_statut}"

    def __str__(self) -> str:
        return self.display


class TaxrefBdcStatutCorTextValues(UnmanagedTaxhubModel):
    id_value_text = models.IntegerField(primary_key=True)
    value = models.ForeignKey(
        TaxrefBdcStatutValues,
        models.DO_NOTHING,
        db_column="id_value",
        related_name="associations_textes",
    )
    text = models.ForeignKey(
        TaxrefBdcStatutText,
        models.DO_NOTHING,
        db_column="id_text",
        related_name="cor_text",
    )

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bdc_statut_cor_text_values")


class TaxrefBdcStatutTaxon(UnmanagedTaxhubModel):
    id = models.IntegerField(primary_key=True)
    value_text = models.ForeignKey(
        TaxrefBdcStatutCorTextValues,
        models.DO_NOTHING,
        db_column="id_value_text",
        related_name="taxons",
    )
    cd_nom = models.IntegerField(null=True, blank=True)
    cd_ref = models.IntegerField(null=True, blank=True)
    rq_statut = models.CharField(null=True, blank=True)

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("bdc_statut_taxons")


class TMetaTaxref(UnmanagedTaxhubModel):
    referencial_name = models.IntegerField(primary_key=True)
    version = models.IntegerField(null=True, blank=True)
    update_date = models.DateTimeField()

    class Meta(UnmanagedTaxhubModel.Meta):
        db_table = table("t_meta_taxref")


# class TaxrefTree(UnmanagedTaxhubModel):
#     taxref = models.OneToOneField(
#         Taxref,
#         models.DO_NOTHING,
#         db_column="cd_nom",
#         primary_key=True,
#         related_name="tree",
#     )
#     path = models.CharField()

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("vm_taxref_tree")

#     def __le__(self, other) -> bool:
#         path, other_path = self.path.split("."), other.path.split(".")
#         return len(path) >= len(other_path) and path[: len(other_path)] == other_path


# class TaxrefLiens(UnmanagedTaxhubModel):
#     pk = models.CompositePrimaryKey("ct_name", "taxon_id", "ct_sp_id")
#     ct_name = models.CharField()
#     ct_type = models.CharField(null=True, blank=True)
#     ct_authors = models.CharField(null=True, blank=True)
#     ct_title = models.CharField(null=True, blank=True)
#     ct_url = models.CharField(null=True, blank=True)
#     taxon = models.ForeignKey(
#         Taxref,
#         models.DO_NOTHING,
#         db_column="cd_nom",
#         related_name="liens",
#     )
#     ct_sp_id = models.CharField()
#     url_sp = models.CharField(null=True, blank=True)

#     class Meta(UnmanagedTaxhubModel.Meta):
#         db_table = table("taxref_liens")
