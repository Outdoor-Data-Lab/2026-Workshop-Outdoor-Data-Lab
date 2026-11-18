"""Import GBIF occurrence downloads (simple CSV format, tab or ";" separated).

One line = one occurrence, identified by its gbifID. GBIF gives taxa in its
own backbone (Catalogue of Life ids such as "3Z5VY", or older numeric GBIF
Backbone ids): the TaxRef cd_ref is found from the scientific name.
Lines without a valid event date are not imported and counted as errors.
"""

import calendar
import csv
import uuid
from datetime import date

import pandas as pd

from ..taxref import find_cd_refs
from .base import BiodiversityRecordParser

COLUMNS = [
    "gbifID",
    "datasetKey",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
    "infraspecificEpithet",
    "taxonRank",
    "scientificName",
    "taxonKey",
    "decimalLatitude",
    "decimalLongitude",
    "coordinateUncertaintyInMeters",
    "eventDate",
]
REQUIRED = [
    "gbifID",
    "taxonKey",
    "kingdom",
    "scientificName",
    "decimalLatitude",
    "decimalLongitude",
]
# Column holding the name without authorship of the higher ranks.
RANK_COLUMNS = {
    "SPECIES": "species",
    "GENUS": "genus",
    "FAMILY": "family",
    "ORDER": "order",
    "CLASS": "class",
    "PHYLUM": "phylum",
    "KINGDOM": "kingdom",
}
# Infraspecific rank markers, as written in TaxRef for plants and fungi.
RANK_MARKERS = {"SUBSPECIES": "subsp.", "VARIETY": "var.", "FORM": "f."}


def date_range(event_date: str) -> tuple[date, date] | None:
    """First and last day of an ISO 8601 event date ("2025-05-24T10:00",
    "1858-04", "1869-05-23/1870-08-19"...); None if it can't be read."""

    def days(part):
        numbers = [int(n) for n in part.split("T")[0].split("-")]
        if len(numbers) == 3:
            return date(*numbers), date(*numbers)
        if len(numbers) == 2:
            year, month = numbers
            return date(year, month, 1), date(
                year, month, calendar.monthrange(year, month)[1]
            )
        if len(numbers) == 1:
            return date(numbers[0], 1, 1), date(numbers[0], 12, 31)
        raise ValueError(part)

    if pd.isna(event_date):
        return None
    start, _, end = event_date.partition("/")
    try:
        bounds = days(start)[0], days(end or start)[1]
    except ValueError:
        return None
    return bounds if bounds[0] <= bounds[1] else None


def name_candidates(taxon: dict) -> list[str]:
    """Names to look for in TaxRef, by priority, for one line of the file."""
    candidates = [taxon["scientificName"]]
    rank, species, epithet = (
        taxon["taxonRank"],
        taxon["species"],
        taxon["infraspecificEpithet"],
    )
    if rank in RANK_MARKERS and pd.notna(species) and pd.notna(epithet):
        candidates += [
            f"{species} {RANK_MARKERS[rank]} {epithet}",  # botanical names
            f"{species} {epithet}",  # zoological names
        ]
    name = taxon.get(RANK_COLUMNS.get(rank))
    if pd.notna(name):
        candidates.append(name)
    return candidates


class GBIFParser(BiodiversityRecordParser):
    NAME = "GBIF"

    def read(self) -> tuple[int, pd.DataFrame]:
        with self.data_import.file.open("rb") as source_file:
            header = source_file.readline().decode("utf-8-sig")
            source_file.seek(0)
            tab = "\t" in header
            data = pd.read_csv(
                source_file,
                sep="\t" if tab else ";",
                # GBIF tab files are not quoted: quotes are part of the values.
                quoting=csv.QUOTE_NONE if tab else csv.QUOTE_MINIMAL,
                dtype=str,
                keep_default_na=False,
                na_values=[""],
                usecols=COLUMNS,
            )

        missing = set(COLUMNS).difference(data.columns)
        if missing:
            raise ValueError(f"Colonnes GBIF manquantes : {', '.join(sorted(missing))}")
        if data.empty:
            raise ValueError("Le fichier GBIF ne contient aucune occurrence.")

        dates = data["eventDate"].map(date_range)
        valid = dates.notna() & data[REQUIRED].notna().all(axis=1)
        data, dates = data[valid], dates[valid]

        taxa = data.drop_duplicates("taxonKey").to_dict("records")
        # return -> {"3Z5VY": 53865, "75R3T": 53911, "6T7B5": 105404, ..., "XXXXX": None}

        cd_refs = find_cd_refs(
            {
                taxon["taxonKey"]: (taxon["kingdom"], name_candidates(taxon))
                for taxon in taxa
            }
        )

        rows = pd.DataFrame(
            {
                "uuid": data["gbifID"].map(
                    lambda gbif_id: uuid.uuid5(
                        uuid.NAMESPACE_URL, f"https://www.gbif.org/occurrence/{gbif_id}"
                    )
                ),
                "cd_ref": data["taxonKey"].map(cd_refs).astype("Int64"),
                "original_id_taxon": data["taxonKey"],
                "referential": data["taxonKey"].map(
                    lambda key: "gbif" if key.isdigit() else "col"
                ),
                "scientific_name": data["scientificName"],
                "record_start_date": dates.str[0],
                "record_end_date": dates.str[1],
                "geom": "POINT("
                + data["decimalLongitude"]
                + " "
                + data["decimalLatitude"]
                + ")",
                "coordinate_uncertainty_in_meters": pd.to_numeric(
                    data["coordinateUncertaintyInMeters"]
                )
                .round()
                .astype("Int64"),
                "dataset_uuid": data["datasetKey"],
            }
        )
        return len(valid), rows
