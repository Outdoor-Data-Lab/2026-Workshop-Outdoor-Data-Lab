from django.db import connection
from django.db.models.expressions import RawSQL
from django_filters import rest_framework as filters

from ..models import DataImport, Practice

# Descendants of the practice whose code is given, at any depth. UNION (not
# UNION ALL) stops on rows already seen, so a cycle cannot loop forever.
DESCENDANTS_SQL = """
    WITH RECURSIVE tree AS (
        SELECT child.id FROM {table} child
        JOIN {table} parent ON child.parent_id = parent.id
        WHERE parent.code = %s
        UNION
        SELECT child.id FROM {table} child JOIN tree ON child.parent_id = tree.id
    )
    SELECT id FROM tree
"""


class PracticeFilter(filters.FilterSet):
    has_parent = filters.BooleanFilter(field_name="parent", lookup_expr="isnull", exclude=True)
    parent_code = filters.CharFilter(method="filter_parent_code")
    # With parent_code: every descendant instead of the direct children only.
    recursive = filters.BooleanFilter(method="filter_recursive")

    class Meta:
        model = Practice
        fields = ["code"]

    def filter_parent_code(self, queryset, name, value):
        if not self.form.cleaned_data.get("recursive"):
            return queryset.filter(parent__code=value)
        table = connection.ops.quote_name(Practice._meta.db_table)
        return queryset.filter(id__in=RawSQL(DESCENDANTS_SQL.format(table=table), [value]))

    def filter_recursive(self, queryset, name, value):
        return queryset  # read by filter_parent_code


class DataImportFilter(filters.FilterSet):
    source_code = filters.CharFilter(field_name="source__code")

    class Meta:
        model = DataImport
        fields = []
