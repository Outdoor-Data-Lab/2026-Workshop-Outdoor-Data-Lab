"""Shared logic of the biodiversity parsers: one imported file -> taxon records."""

import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from commons.models import DataImport

from ..models import TaxonomicReferential, TaxonRecord

# Every field but the keys is overwritten when a record is imported again.
UPDATED_FIELDS = [
    field.name
    for field in TaxonRecord._meta.concrete_fields
    if not field.primary_key and field.name != "uuid"
]
BATCH_SIZE = 5000


class BiodiversityRecordParser:
    """Base class of the parsers that import taxon records.

    A subclass only reads its file, in `read()`, which returns:
    - the number of lines read in the file (saved in DataImport.line_numbers);
    - a DataFrame with one row per observation, whose columns are TaxonRecord
      fields except `id` and `source` (set here), with:
      - `uuid`: required, the key used to find records already imported;
      - `geom`: a geometry as a WKT string in EPSG:4326, e.g.
        "POINT(6.5 44.85)" (anything GEOSGeometry reads: WKB, EWKT,
        GeoJSON... but not a shapely object);
      - `referential`: a TaxonomicReferential code, e.g. "taxref";
      - missing values (NaN, pd.NA) saved as NULL.

    `import_data()` then saves the rows the same way for every source: records
    are upserted on their uuid, so a re-import updates the observations
    already imported instead of duplicating them.
    """

    NAME = ""  # used in error messages

    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.source = data_import.source

    def read(self) -> tuple[int, pd.DataFrame]:
        raise NotImplementedError

    def import_data(self) -> int:
        """Save the records read from the file; return their number."""
        line_count, rows = self.read()
        referentials = self._referentials(rows["referential"])
        # Missing values (NaN, pd.NA) become None, i.e. NULL.
        records = rows.astype(object).where(rows.notna(), None).to_dict("records")

        with transaction.atomic():
            TaxonRecord.objects.bulk_create(
                (
                    TaxonRecord(
                        **record
                        | {
                            "source": self.source,
                            "referential": referentials[record["referential"]],
                            "geom": GEOSGeometry(record["geom"], srid=4326),
                        }
                    )
                    for record in records
                ),
                batch_size=BATCH_SIZE,
                update_conflicts=True,
                unique_fields=["uuid"],
                update_fields=UPDATED_FIELDS,
            )
            self.data_import.line_numbers = line_count
            self.data_import.error_numbers = 0
            self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        return len(rows)

    def _referentials(self, codes: pd.Series) -> dict[str, TaxonomicReferential]:
        by_code = TaxonomicReferential.objects.in_bulk(set(codes), field_name="code")
        unknown = set(codes).difference(by_code)
        if unknown:
            raise ValueError(
                f"Référentiels {self.NAME} inconnus : {', '.join(sorted(unknown))}"
            )
        return by_code
