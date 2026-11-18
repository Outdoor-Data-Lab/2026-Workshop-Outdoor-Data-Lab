"""Shared logic of the biodiversity parsers: one imported file -> taxon records."""

import pandas as pd
from django.contrib.gis.geos import GEOSGeometry

from commons.parsers import ImportParser

from ..models import TaxonomicReferential, TaxonRecord

# Every field but the keys is overwritten when a record is imported again.
UPDATED_FIELDS = [
    field.name
    for field in TaxonRecord._meta.concrete_fields
    if not field.primary_key and field.name != "uuid"
]
BATCH_SIZE = 5000


class BiodiversityRecordParser(ImportParser):
    """Base class of the parsers that import taxon records (see commons.parsers.ImportParser).

    A subclass only reads its file, in `read()`, which returns:
    - the number of lines read in the file (saved in DataImport.line_numbers);
      lines read but not returned are counted in DataImport.error_numbers;
    - a DataFrame with one row per observation, whose columns are TaxonRecord
      fields except `id` and `source` (set here), with:
      - `uuid`: required, the key used to find records already imported;
      - `geom`: a geometry as a WKT string in EPSG:4326, e.g.
        "POINT(6.5 44.85)" (anything GEOSGeometry reads: WKB, EWKT,
        GeoJSON... but not a shapely object);
      - `referential`: a TaxonomicReferential code, e.g. "taxref";
      - missing values (NaN, pd.NA) saved as NULL.

    `save()` then writes the rows the same way for every source: records
    are upserted on their uuid, so a re-import updates the observations
    already imported instead of duplicating them.
    """

    def save(self, rows: pd.DataFrame) -> None:
        """Upsert the records on their uuid, by batch.

        bulk_create() builds all its objects before writing them: one call per
        batch keeps large files (hundreds of thousands of rows) in memory.
        """
        referentials = self._referentials(rows["referential"])
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows.iloc[start : start + BATCH_SIZE]
            # Missing values (NaN, pd.NA) become None, i.e. NULL.
            records = batch.astype(object).where(batch.notna(), None).to_dict("records")
            TaxonRecord.objects.bulk_create(
                [
                    TaxonRecord(
                        **record
                        | {
                            "source": self.source,
                            "data_import": self.data_import,
                            "referential": referentials[record["referential"]],
                            "geom": GEOSGeometry(record["geom"], srid=4326),
                        }
                    )
                    for record in records
                ],
                update_conflicts=True,
                unique_fields=["uuid"],
                update_fields=UPDATED_FIELDS,
            )

    def _referentials(self, codes: pd.Series) -> dict[str, TaxonomicReferential]:
        by_code = TaxonomicReferential.objects.in_bulk(set(codes), field_name="code")
        unknown = set(codes).difference(by_code)
        if unknown:
            raise ValueError(
                f"Unknown {self.NAME} referentials: {', '.join(sorted(unknown))}"
            )
        return by_code
