"""Shared logic of the traffic parsers: one imported file -> counting objects and measures.

A parser only reads its file: `read()` returns the number of lines read and one
row per measure, with the columns of MEASURE_COLUMNS. Lines it deliberately skips
are counted in `skipped_lines` and saved as the import's error_numbers.

Saving is the same for every source: missing objects are created in bulk, and
measures are upserted on their key (object, start, end, practice, unit). A
re-import updates the count of the measures it contains and leaves the others:
a yearly and a daily measure of the same edge, or two practices over the same
period, never replace each other. A measure missing from the new file is kept.
"""

from abc import ABC, abstractmethod

import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from commons.models import DataImport, Practice

from ..models import MEASURE_KEY, CountingMeasure, CountingObject, CountingObjectType, Unit

MEASURE_COLUMNS = ["external_id", "geometry", "start_datetime", "end_datetime", "count", "activity"]
BATCH_SIZE = 5000


class TrafficParser(ABC):
    NAME = ""  # used in error messages
    EXAMPLE = ""  # expected file, shown in the admin when the source is selected
    PRACTICE_CODES: dict[str, str] = {}  # source activity -> Practice code
    OBJECT_TYPE = "segment"
    UNIT = "person"

    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.source = data_import.source
        self.skipped_lines = 0

    @abstractmethod
    def read(self) -> tuple[int, pd.DataFrame]:
        """Read the file: return the number of lines read and the rows to save."""

    def import_data(self) -> int:
        """Save the measures read from the file; return their number."""
        line_count, rows = self.read()
        missing = set(MEASURE_COLUMNS).difference(rows.columns)
        if missing:
            raise ValueError(f"{type(self).__name__}.read() sans les colonnes : {', '.join(sorted(missing))}")
        practices = self._practices(rows["activity"])
        self._check_no_duplicates(rows)
        object_type = CountingObjectType.objects.get(code=self.OBJECT_TYPE)
        unit = Unit.objects.get(code=self.UNIT)

        with transaction.atomic():
            object_ids = self._save_objects(rows, object_type)
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
                update_conflicts=True,
                unique_fields=MEASURE_KEY,
                update_fields=["count", "date_update"],
            )
            self.data_import.line_numbers = line_count
            self.data_import.error_numbers = self.skipped_lines
            self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        return len(rows)

    def _practices(self, activities: pd.Series) -> dict[str, Practice]:
        unknown = set(activities).difference(self.PRACTICE_CODES)
        if unknown:
            raise ValueError(f"Activités {self.NAME} inconnues : {', '.join(sorted(unknown))}")
        by_code = Practice.objects.in_bulk(set(self.PRACTICE_CODES.values()), field_name="code")
        return {activity: by_code[code] for activity, code in self.PRACTICE_CODES.items()}

    def _check_no_duplicates(self, rows: pd.DataFrame) -> None:
        """Refuse a file giving two counts for the same measure key: the upsert would keep only one."""
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

    def _save_objects(self, rows, object_type) -> dict[str, int]:
        """Create the objects not imported yet; return the ids of all objects by external id."""
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
        return dict(objects.values_list("external_id", "id"))
