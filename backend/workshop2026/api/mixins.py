
from django_filters import filters, FilterSet
from rest_framework.exceptions import ValidationError

from ref_geo.models import LArea


class DynamicFieldsMixin:
    fields_query_param = "fields"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        if request is None or request.method not in ("GET", "HEAD", "OPTIONS"):
            return

        raw = request.query_params.get(self.fields_query_param)
        if not raw:
            return

        requested = {f.strip() for f in raw.split(",") if f.strip()}
        always_keep = {getattr(self.Meta, "geo_field", None)} - {None}

        for name in set(self.fields) - requested - always_keep:
            self.fields.pop(name)


class AreaFilterSet(FilterSet):
    """FilterSet pour les filtres par zone géographique."""

    area_code = filters.CharFilter(
        method="filter_by_area_code",
        label="Area code",
        help_text="Filter by area code (e.g., '26')"
    )
    area_id = filters.NumberFilter(
        method="filter_by_area_id",
        label="Area ID",
        help_text="Filter by area ID"
    )

    def filter_by_area_code(self, queryset, name, value):
        """Filter by area code (e.g., '26')."""
        try:
            area = LArea.objects.get(area_code=value)
            return queryset.filter(geom__intersects=area.geom_4326)
        except LArea.DoesNotExist:
            raise ValidationError(
                {"area_code": f"Area with code '{value}' does not exist."}
            )

    def filter_by_area_id(self, queryset, name, value):
        """Filter by area ID (e.g., 12345)."""
        try:
            area = LArea.objects.get(id_area=value)
            return queryset.filter(geom__intersects=area.geom_4326)
        except LArea.DoesNotExist:
            raise ValidationError(
                {"area_id": f"Area with ID '{value}' does not exist."}
            )

    class Meta:
        model = None  # À définir dans les sous-classes
        fields = []