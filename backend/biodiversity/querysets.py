from django.conf import settings
from django.contrib.postgres.expressions import ArraySubquery
from django.db import connection
from django.db.models import (
    Count,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce, JSONObject

from ref_geo.models import BibAreasType, LArea
from taxhub.models import Taxref, VBdcStatus

from .models import TaxonRecord

# NOTE
# API Carto, nombre de taxons menacés uniquement
# API Consultation par zone, liste des taxons

# Taxon status querysets. The status view can contain several rows for the
# same reference taxon; consumers must therefore count distinct cd_ref values.
REDLIST_FILTER = Q(
    cd_type_statut="LRN",
    code_statut__in=("RE", "RE?", "CR", "VU", "EN", "EX"),
)

PROTECTION_FILTER = Q(
    cd_type_statut="PN",
    lb_type_statut="Protection nationale",
)

REDLIST_STATUS = VBdcStatus.objects.filter(REDLIST_FILTER).values(
    "cd_ref", "code_statut", "cd_type_statut"
)

PROTECTION_STATUS = VBdcStatus.objects.filter(PROTECTION_FILTER).values(
    "cd_ref", "code_statut", "cd_type_statut", "lb_type_statut"
)

PROTECTION_OR_REDLIST_STATUS = VBdcStatus.objects.filter(
    PROTECTION_FILTER | REDLIST_FILTER
).values("cd_ref", "code_statut", "cd_type_statut")


def cells_with_status_taxa(statuses: QuerySet = PROTECTION_OR_REDLIST_STATUS):
    """Ids of the default grid cells holding an observation of a taxon with one of
    ``statuses``, for ``id_area__in``.

    From the few observations with a status to their cells, through the spatial
    index of the cells: on 22,000 cells of 500 m, 1.6 s instead of 32 s for a
    count per cell then a filter. SQL: Django has no spatial join between two
    unrelated models.
    """
    quote = connection.ops.quote_name
    status_sql, status_params = statuses.values("cd_ref").query.sql_with_params()
    sql = f"""
        SELECT DISTINCT cell.id_area
        FROM {quote(TaxonRecord._meta.db_table)} record
        JOIN {quote(LArea._meta.db_table)} cell
          ON cell.id_type = (SELECT id_type FROM {quote(BibAreasType._meta.db_table)} WHERE type_code = %s)
         AND ST_Intersects(cell.geom_4326, record.geom)
        WHERE record.cd_ref IN ({status_sql})
    """
    return RawSQL(sql, (settings.DEFAULT_GRID_AREA_TYPE, *status_params))


def _status_list(*filters: Q):
    """Return distinct status labels for the taxon in the outer query."""

    statuses = (
        VBdcStatus.objects.filter(*filters, cd_ref=OuterRef("cd_ref"))
        .order_by()
        .annotate(
            status=JSONObject(
                lb_type_statut="lb_type_statut",
                code_statut="code_statut",
                label_statut="label_statut",
            )
        )
        .values("status")
        .distinct()
    )
    return ArraySubquery(statuses)


def _taxon_count(statuses: QuerySet):
    """Count distinct reference taxa with a status in the outer area."""

    taxa = (
        TaxonRecord.objects.filter(
            cd_ref__isnull=False,
            cd_ref__in=statuses.values("cd_ref"),
            geom__intersects=OuterRef("geom_4326"),
        )
        .order_by()
        .annotate(_group=Value(1))
        .values("_group")
        .annotate(total=Count("cd_ref", distinct=True))
        .values("total")
    )
    return Coalesce(
        Subquery(taxa, output_field=IntegerField()),
        Value(0),
    )


def with_taxon_status_counts(queryset=None):
    """Annotate areas with distinct protected and threatened taxon counts."""

    if queryset is None:
        queryset = LArea.objects.all()

    return queryset.annotate(
        protected_taxa_count=_taxon_count(PROTECTION_STATUS),
        threatened_taxa_count=_taxon_count(REDLIST_STATUS),
        protected_or_threatened_taxa_count=_taxon_count(PROTECTION_OR_REDLIST_STATUS),
    )


def with_taxa(queryset=None):
    """Annotate areas with their observed protected or threatened taxa."""

    if queryset is None:
        queryset = LArea.objects.all()

    taxref = Taxref.objects.filter(cd_nom=OuterRef("cd_ref"))
    taxa = (
        TaxonRecord.objects.filter(
            cd_ref__isnull=False,
            cd_ref__in=PROTECTION_OR_REDLIST_STATUS.values("cd_ref"),
            geom__intersects=OuterRef("geom_4326"),
        )
        .order_by()
        .values("cd_ref")
        .annotate(
            count=Count("pk"),
            date_min=Min("record_start_date"),
            date_max=Max("record_end_date"),
            lb_nom=Subquery(taxref.values("lb_nom")[:1]),
            nom_vern=Subquery(taxref.values("nom_vern")[:1]),
            protection=_status_list(PROTECTION_FILTER),
            threatened=_status_list(REDLIST_FILTER),
        )
        .annotate(
            taxon=JSONObject(
                cd_ref="cd_ref",
                lb_nom="lb_nom",
                nom_vern="nom_vern",
                protection="protection",
                threatened="threatened",
                count="count",
                date_min="date_min",
                date_max="date_max",
            )
        )
        .order_by("cd_ref")
        .values("taxon")
    )
    return queryset.annotate(taxa=ArraySubquery(taxa))


AREAS_WITH_TAXON_STATUS_COUNTS = with_taxon_status_counts()

# One LArea instance per grid cell of the configured type.
BASE_GRID = (
    LArea.objects.filter(type__type_code=settings.DEFAULT_GRID_AREA_TYPE)
    .select_related("type")
    .defer("geom", "centroid")
)

GRID = with_taxon_status_counts(BASE_GRID)
TAXA_GRID = with_taxa(BASE_GRID)
