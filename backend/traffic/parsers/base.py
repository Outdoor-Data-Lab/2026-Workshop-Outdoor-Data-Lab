"""Shared logic of the traffic parsers: one imported file -> counting objects and measures.

A parser only reads its file: `read()` returns the number of lines read and one
row per measure, with the columns of MEASURE_COLUMNS. Saving is the same for
every source: missing objects are created in bulk, and a re-import replaces the
measures of the same objects over the same period instead of duplicating them.
"""

import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from commons.models import DataImport, Practice

from ..models import CountingMeasure, CountingObject, CountingObjectType, Unit

MEASURE_COLUMNS = ["external_id", "geometry", "start_datetime", "end_datetime", "count", "activity"]
BATCH_SIZE = 5000


class TrafficParser:
    NAME = ""  # used in error messages
    PRACTICE_CODES: dict[str, str] = {}  # source activity -> Practice code
    OBJECT_TYPE = "segment"
    UNIT = "person"

    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.source = data_import.source

    def read(self) -> tuple[int, pd.DataFrame]:
        raise NotImplementedError

    def import_data(self) -> int:
        """Save the measures read from the file; return their number."""
        line_count, rows = self.read()
        practices = self._practices(rows["activity"])
        object_type = CountingObjectType.objects.get(code=self.OBJECT_TYPE)
        unit = Unit.objects.get(code=self.UNIT)

        with transaction.atomic():
            object_ids, existing_ids = self._save_objects(rows, object_type)
            self._delete_previous_measures(rows, existing_ids)
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
            self.data_import.line_numbers = line_count
            self.data_import.error_numbers = 0
            self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        return len(rows)

    def _practices(self, activities: pd.Series) -> dict[str, Practice]:
        unknown = set(activities).difference(self.PRACTICE_CODES)
        if unknown:
            raise ValueError(f"Activités {self.NAME} inconnues : {', '.join(sorted(unknown))}")
        by_code = Practice.objects.in_bulk(set(self.PRACTICE_CODES.values()), field_name="code")
        return {activity: by_code[code] for activity, code in self.PRACTICE_CODES.items()}

    def _save_objects(self, rows, object_type) -> tuple[dict[str, int], list[int]]:
        """Create the objects not imported yet; return all ids by external id and the ids that existed."""
        objects = CountingObject.objects.filter(source=self.source)
        known = dict(objects.values_list("external_id", "id"))
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
        existing = [known[uid] for uid in rows.external_id.unique() if uid in known]
        return dict(objects.values_list("external_id", "id")), existing

    def _delete_previous_measures(self, rows, existing_ids: list[int]) -> None:
        """Delete the measures of already known objects over the imported period."""
        start, end = rows.start_datetime.min(), rows.end_datetime.max()
        for i in range(0, len(existing_ids), BATCH_SIZE):
            CountingMeasure.objects.filter(
                counting_object_id__in=existing_ids[i : i + BATCH_SIZE],
                start_datetime__lt=end,
                end_datetime__gt=start,
            ).delete()
