"""Shared logic of the traffic parsers: one imported file -> counting objects and measures.

A parser only reads its file (see commons.parsers.ImportParser): `read()` returns
the number of lines read and one row per measure, with the columns of
MEASURE_COLUMNS. A row may gather several lines (the pieces of a track), so the
lines deliberately skipped are counted in `skipped_lines`, saved as the
import's error_numbers.

Saving is the same for every source: missing objects are created in bulk, and
the measures the file gives again are replaced: those of an already known object
with the same start, end, practice and unit are deleted before the file's
measures are inserted. A re-import thus replaces the measures it contains and
leaves the others: a yearly and a daily measure of the same edge, or two
practices over the same period, never replace each other. A measure missing
from the new file is kept.

Nothing in the database forbids two measures with the same key: only the
parsers avoid creating them.
"""

import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection

from commons.models import DataImport, Practice
from commons.parsers import ImportParser

from ..models import CountingMeasure, CountingObject, CountingObjectType, Unit

MEASURE_COLUMNS = ["external_id", "geometry", "start_datetime", "end_datetime", "count", "activity"]
BATCH_SIZE = 5000


class TrafficParser(ImportParser):
    PRACTICE_CODES: dict[str, str] = {}  # source activity -> Practice code
    OBJECT_TYPE = "segment"
    UNIT = "person"

    def __init__(self, data_import: DataImport):
        super().__init__(data_import)
        self.skipped_lines = 0

    def error_count(self, line_count: int, rows: pd.DataFrame) -> int:
        return self.skipped_lines

    def save(self, rows: pd.DataFrame) -> None:
        """Create the missing counting objects, then replace the measures the file gives again."""
        missing = set(MEASURE_COLUMNS).difference(rows.columns)
        if missing:
            raise ValueError(f"{type(self).__name__}.read() sans les colonnes : {', '.join(sorted(missing))}")
        practices = self._practices(rows["activity"])
        self._check_no_duplicates(rows)
        object_type = CountingObjectType.objects.get(code=self.OBJECT_TYPE)
        unit = Unit.objects.get(code=self.UNIT)

        object_ids, known = self._save_objects(rows, object_type)
        self._delete_given_measures(rows[rows.external_id.isin(known)], object_ids, practices, unit)
        CountingMeasure.objects.bulk_create(
            (
                CountingMeasure(
                    counting_object_id=object_ids[row.external_id],
                    start_datetime=row.start_datetime,
                    end_datetime=row.end_datetime,
                    count=row.count,
                    unit=unit,
                    practice=practices[row.activity],
                )
                for row in rows.itertuples()
            ),
            batch_size=BATCH_SIZE,
        )

    def _practices(self, activities: pd.Series) -> dict[str, Practice]:
        unknown = set(activities).difference(self.PRACTICE_CODES)
        if unknown:
            raise ValueError(f"Activités {self.NAME} inconnues : {', '.join(sorted(unknown))}")
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
                f"Mesures {self.NAME} en double (même objet, période et pratique) : {duplicated.sum()}, "
                f"par exemple {first.external_id} à partir du {first.start_datetime}."
            )

    def _save_objects(self, rows, object_type) -> tuple[dict[str, int], set[str]]:
        """Create the objects not imported yet; return the ids of all objects by
        external id, and the external ids of the objects that already existed."""
        objects = CountingObject.objects.filter(source=self.source)
        known = set(objects.values_list("external_id", flat=True))
        new = rows.drop_duplicates("external_id").loc[lambda r: ~r.external_id.isin(known)]
        CountingObject.objects.bulk_create(
            (
                CountingObject(
                    source=self.source,
                    type=object_type,
                    external_id=row.external_id,
                    geom=GEOSGeometry(memoryview(row.geometry.wkb), srid=4326),
                )
                for row in new.itertuples()
            ),
            batch_size=BATCH_SIZE,
        )
        return dict(objects.values_list("external_id", "id")), known

    def _delete_given_measures(self, rows, object_ids, practices, unit) -> None:
        """Delete the measures that the rows give again: same object, start, end, practice and unit."""
        table = connection.ops.quote_name(CountingMeasure._meta.db_table)
        # One query per batch: the keys are passed as arrays, and the lookup uses
        # the (counting_object, start_datetime) index.
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
