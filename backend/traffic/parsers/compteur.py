"""Import hourly counts of automatic counters into the traffic application.

Input: the long CSV (plain or zipped), one line per counter and per hour:
date_debut, object_name, count, geom (WKT point). It is not the raw counter
export: it is built from the raw hourly files (one column per counter) and the
counters' GPS positions by the standalone script compteurs_to_csv.py:

    uv run python backend/traffic/parsers/compteurs_to_csv.py 2024_tous-sites.csv \
        --gps positions.csv -o compteurs_long.csv

positions.csv needs the columns object_name, lat, lon.

One counter = one counting object with one measure per hour.
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .base import TrafficParser

REQUIRED_COLUMNS = ["date_debut", "object_name", "count", "geom"]


class CompteurParser(TrafficParser):
    LABEL = "Hourly counter CSV"
    NAME = "counter"
    CONTENT = "Holds points: one automatic counter per position, with its number of passages per hour."
    EXAMPLE = (
        "Hourly long CSV, alone or zipped (columns date_debut, object_name, count, geom). E.g. "
        "compteurs_cleaned.zip. Not the raw export: it is produced from the raw files "
        "by the script backend/traffic/parsers/compteurs_to_csv.py."
    )
    PRACTICE_CODES = {"hiking": "hiking"}
    OBJECT_TYPE = "counter"

    def read(self) -> tuple[int, pd.DataFrame]:
        path = Path(self.data_import.file.path)
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if len(csv_names) != 1:
                    raise ValueError("The counter archive must hold a single .csv.")
                with archive.open(csv_names[0]) as csv_file:
                    lines = pd.read_csv(csv_file)
        else:
            lines = pd.read_csv(path)

        missing = set(REQUIRED_COLUMNS).difference(lines.columns)
        if missing:
            raise ValueError(f"Missing columns in the counter file: {', '.join(sorted(missing))}")
        if lines.empty:
            raise ValueError("The counter file holds no data.")
        if "activity" not in lines:
            lines["activity"] = "hiking"

        # Hours are local time without offset: a 2-hour gap on the last Sunday of
        # March (summer time) proves it. Read them as Europe/Paris and store UTC.
        # The repeated hour of the October change appears only once: it is taken
        # as summer time (ambiguous=True); the missing March hour cannot exist.
        start = pd.to_datetime(lines["date_debut"], errors="coerce")
        if start.isna().any():
            raise ValueError("Some date_debut values are not valid dates.")
        start = start.dt.tz_localize("Europe/Paris", ambiguous=True, nonexistent="NaT")

        # Counters without position cannot be stored (geometry is required): skipped.
        no_geom = lines["geom"].isna()
        # The CSV generator fills missing hours with 0 (fillna), so a counter at 0
        # all year has no data at all, not zero passages: skipped. Other zeros are
        # kept although some are probably outages, as they cannot be told apart.
        no_data = lines.groupby("object_name")["count"].transform("sum") == 0
        keep = ~no_geom & ~no_data & start.notna()
        self.skipped_lines = int((~keep).sum())

        kept = lines[keep]
        rows = pd.DataFrame(
            {
                "external_id": kept["object_name"].astype(str),
                "geometry": gpd.GeoSeries.from_wkt(kept["geom"]).values,
                "start_datetime": start[keep].dt.tz_convert("UTC"),
                "end_datetime": start[keep].dt.tz_convert("UTC") + pd.Timedelta(hours=1),
                "count": kept["count"].astype(int),
                "activity": kept["activity"],
            }
        )
        return len(lines), rows
