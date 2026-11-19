"""Shared logic of the traffic parsers: one imported file -> counting objects and measures.

A parser only reads its file (see commons.parsers.ImportParser): `read()` returns
the number of lines read and one row per measure, with the columns of
MEASURE_COLUMNS. A row may gather several lines (the pieces of a track), so the
lines deliberately skipped are counted in `skipped_lines`, saved as the
import's error_numbers. An optional `origin` column names the application that
produced the row (OutdoorVision's provider): it becomes the origin of the
object it creates, a DataSource found by code or label, or created with no
domain (an origin only).

Saving is the same for every source: missing objects are created in bulk, and
the measures the file gives again are replaced: those of an already known object
with the same start, end, practice and unit are deleted before the file's
measures are inserted. A re-import thus replaces the measures it contains and
leaves the others: a yearly and a daily measure of the same edge, or two
practices over the same period, never replace each other. A measure missing
from the new file is kept.

The database forbids two measures with the same key (constraint
counting_measure_unique_key).
"""

import logging
from itertools import batched

import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection, transaction
from django.db.models import Q
from django.utils.text import slugify

from commons.models import DataImport, DataSource, Practice
from commons.parsers import ImportParser

from ..areas import refresh_cell_day_counts
from ..models import CountingMeasure, CountingObject, CountingObjectType, Unit

logger = logging.getLogger(__name__)

MEASURE_COLUMNS = ["external_id", "geometry", "start_datetime", "end_datetime", "count", "activity"]
BATCH_SIZE = 5000


def _refresh_cell_counts():
    try:
        refresh_cell_day_counts()
    except Exception:  # the import is saved: the scores fall back to the measures
        logger.exception("Could not refresh the precomputed cell counts")


class TrafficParser(ImportParser):
    PRACTICE_CODES: dict[str, str] = {}  # source activity -> Practice code
    OBJECT_TYPE = "segment"
    UNIT = "person"

    def __init__(self, data_import: DataImport):
        super().__init__(data_import)
        self.skipped_lines = 0

    def error_count(self, line_count: int, rows: pd.DataFrame) -> int:
        return self.skipped_lines

    def import_data(self) -> int:
        saved = super().import_data()
        # The scores read precomputed counts (CellDayCount): rebuild them once the
        # import is committed. Until then they notice they are stale and read the measures.
        transaction.on_commit(_refresh_cell_counts)
        return saved

    def save(self, rows: pd.DataFrame) -> None:
        """Create the missing counting objects, then replace the measures the file gives again."""
        missing = set(MEASURE_COLUMNS).difference(rows.columns)
        if missing:
            raise ValueError(f"{type(self).__name__}.read() without the columns: {', '.join(sorted(missing))}")
        practices = self._practices(rows["activity"])
        self._check_no_duplicates(rows)
        object_type = CountingObjectType.objects.get(code=self.OBJECT_TYPE)
        unit = Unit.objects.get(code=self.UNIT)

        object_ids, known = self._save_objects(rows, object_type, self._origins(rows))
        self._delete_given_measures(rows[rows.external_id.isin(known)], object_ids, practices, unit)
        measures = (
            CountingMeasure(
                counting_object_id=object_ids[row.external_id],
                start_datetime=row.start_datetime,
                end_datetime=row.end_datetime,
                count=row.count,
                unit=unit,
                practice=practices[row.activity],
                data_import=self.data_import,
            )
            for row in rows.itertuples()
        )
        # One call per batch: bulk_create() builds all its objects before writing
        # them, which does not fit in memory for millions of measures.
        for batch in batched(measures, BATCH_SIZE):
            CountingMeasure.objects.bulk_create(batch)

    def _practices(self, activities: pd.Series) -> dict[str, Practice]:
        unknown = set(activities).difference(self.PRACTICE_CODES)
        if unknown:
            raise ValueError(f"Unknown {self.NAME} activities: {', '.join(sorted(unknown))}")
        by_code = Practice.objects.in_bulk(set(self.PRACTICE_CODES.values()), field_name="code")
        return {activity: by_code[code] for activity, code in self.PRACTICE_CODES.items()}

    def _check_no_duplicates(self, rows: pd.DataFrame) -> None:
        """Refuse a file giving two counts for the same measure key: both would be added up."""
        key = rows[["external_id", "start_datetime", "end_datetime"]].assign(
            practice=rows["activity"].map(self.PRACTICE_CODES)
        )
        duplicated = key.duplicated()
        if duplicated.any():
            first = rows[duplicated].iloc[0]
            raise ValueError(
                f"Duplicate {self.NAME} measures (same object, period and practice): {duplicated.sum()}, "
                f"e.g. {first.external_id} from {first.start_datetime}."
            )

    def _origins(self, rows: pd.DataFrame) -> dict[str, DataSource]:
        """The DataSource of each name of the `origin` column, created if missing."""
        if "origin" not in rows:
            return {}
        origins = {}
        for name in rows["origin"].dropna().unique():
            code = slugify(name).replace("-", "_")
            origins[name] = DataSource.objects.filter(Q(code=code) | Q(label__iexact=name)).first()
            if origins[name] is None:
                origins[name] = DataSource.objects.create(code=code, label=name)
        return origins

    def _save_objects(self, rows, object_type, origins) -> tuple[dict[str, int], set[str]]:
        """Create the objects not imported yet; return the ids of all objects by
        external id, and the external ids of the objects that already existed."""
        objects = CountingObject.objects.filter(source=self.source)
        known = set(objects.values_list("external_id", flat=True))
        new = rows.drop_duplicates("external_id").loc[lambda r: ~r.external_id.isin(known)]
        new_objects = (
            CountingObject(
                source=self.source,
                type=object_type,
                external_id=row.external_id,
                origin=origins.get(getattr(row, "origin", None)),
                geom=GEOSGeometry(memoryview(row.geometry.wkb), srid=4326),
                data_import=self.data_import,
            )
            for row in new.itertuples()
        )
        for batch in batched(new_objects, BATCH_SIZE):
            CountingObject.objects.bulk_create(batch)
        return dict(objects.values_list("external_id", "id")), known

    def _delete_given_measures(self, rows, object_ids, practices, unit) -> None:
        """Delete the measures that the rows give again: same object, start, end, practice and unit."""
        table = connection.ops.quote_name(CountingMeasure._meta.db_table)
        # One query per batch: the keys are passed as arrays, and the lookup uses
        # the index of counting_measure_unique_key.
        sql = f"""
            DELETE FROM {table} AS m
            USING unnest(%s::bigint[], %s::timestamptz[], %s::timestamptz[], %s::bigint[])
                AS k(object_id, start_at, end_at, practice_id)
            WHERE m.counting_object_id = k.object_id AND m.start_datetime = k.start_at
              AND m.end_datetime = k.end_at AND m.practice_id = k.practice_id AND m.unit_id = %s
        """
        with connection.cursor() as cursor:
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows.iloc[i : i + BATCH_SIZE]
                cursor.execute(
                    sql,
                    [
                        [object_ids[uid] for uid in batch.external_id],
                        [start.to_pydatetime() for start in batch.start_datetime],
                        [end.to_pydatetime() for end in batch.end_datetime],
                        [practices[activity].pk for activity in batch.activity],
                        unit.pk,
                    ],
                )
