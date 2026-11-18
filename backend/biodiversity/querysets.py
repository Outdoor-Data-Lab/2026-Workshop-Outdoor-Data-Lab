from django.db.models import (
    Count,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.conf import settings
from ref_geo.models import LArea
from taxhub.models import VBdcStatus

from .models import TaxonRecord


# Taxon status querysets. The status view can contain several rows for the
# same reference taxon; consumers must therefore count distinct cd_ref values.
REDLIST_STATUS = VBdcStatus.objects.filter(
    cd_type_statut__in=("LRR", "LRN"),
    code_statut__in=("RE", "RE?", "CR", "VU", "EN", "EX"),
).values("cd_ref", "code_statut", "cd_type_statut")

PROTECTION_STATUS = VBdcStatus.objects.filter(
    cd_type_statut="PN",
).values("cd_ref", "code_statut", "cd_type_statut")

PROTECTION_OR_REDLIST_STATUS = VBdcStatus.objects.filter(
    Q(cd_type_statut="PN")
    | Q(
        cd_type_statut__in=("LRR", "LRN"),
        code_statut__in=("RE", "RE?", "CR", "VU", "EN", "EX"),
    )
).values("cd_ref", "code_statut", "cd_type_statut")


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
        protected_or_threatened_taxa_count=_taxon_count(
            PROTECTION_OR_REDLIST_STATUS
        ),
    )


AREAS_WITH_TAXON_STATUS_COUNTS = with_taxon_status_counts()

# One LArea instance per 1 km grid cell, including the three taxon counters.
GRID = with_taxon_status_counts(
    LArea.objects.filter(type__type_code=settings.DEFAULT_AREA_TYPE)
    .select_related("type")
    .defer("geom", "centroid")
)
