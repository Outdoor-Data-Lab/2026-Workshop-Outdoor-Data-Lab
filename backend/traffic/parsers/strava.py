"""Import Strava Metro exports into the traffic application.

One zip = a shapefile of the edges network (edgeUID, geometry) and a CSV of
counts (total_trip_count = passages), one line per used edge and per period:
- yearly exports (all_edges_yearly_*): a `year` column, one line per edge;
- daily exports (all_edges_daily_*, usually a quarter): a `date` column, one line
  per edge and per day.
One used edge = one counting object, with one measure per year or per day.

The edges network depends on the Strava basemap version (the .txt of the zip):
two exports on different basemaps share no edgeUID, so the same path then gets
one counting object per basemap.
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .base import TrafficParser

CSV_COLUMNS = ["edge_uid", "activity_type", "total_trip_count"]
# Period column -> length of the period. Dates are local days: read as Europe/Paris.
PERIODS = {"year": pd.DateOffset(years=1), "date": pd.DateOffset(days=1)}


class StravaParser(TrafficParser):
    LABEL = "Strava Metro export (zip)"
    NAME = "Strava"
    CONTENT = (
        "Holds trail and road edges (lines of the Strava network), with their number "
        "of passages per year or per day. Pedestrian exports (Run, Walk, Hike) only."
    )
    EXAMPLE = (
        "Yearly or daily Strava Metro zip (shapefile + CSV). E.g. all_edges_yearly_2020_ped_savoie.zip, "
        "all_edges_daily_2021-07-01-2021-09-30_ped_HA.zip. One zip = one export (one .shp and one .csv). "
        "A zip of zips (strava_isere.zip) must be unzipped first."
    )
    PRACTICE_CODES = {
        # TODO: inexact, "Run,Walk,Hike" mixes walking and running. Replace by a
        # practice grouping both (e.g. "pédestre") once it exists.
        "Run,Walk,Hike": "walking",
    }

    def read(self) -> tuple[int, pd.DataFrame]:
        path = Path(self.data_import.file.path)
        if not zipfile.is_zipfile(path):
            raise ValueError("The Strava file must be a zip (shapefile + CSV).")
        with zipfile.ZipFile(path) as archive:
            # Exactly one export per zip: with several CSVs, only one would be imported.
            files = [name for name in archive.namelist() if not name.startswith("__MACOSX/")]
            found = {
                suffix: [name for name in files if name.lower().endswith(suffix)] for suffix in (".shp", ".csv", ".zip")
            }
            if found[".zip"]:
                raise ValueError("The Strava archive holds other zips: unzip it and import each of them.")
            if len(found[".shp"]) != 1 or len(found[".csv"]) != 1:
                raise ValueError(
                    "The Strava archive must hold a single export, i.e. one .shp and one .csv "
                    f"(found: {len(found['.shp'])} .shp and {len(found['.csv'])} .csv)."
                )
            (shp_name,), (csv_name,) = found[".shp"], found[".csv"]
            with archive.open(csv_name) as csv_file:
                header = pd.read_csv(csv_file, nrows=0).columns
            period = next((column for column in PERIODS if column in header), None)
            if period is None:
                raise ValueError("The Strava CSV must have a year or date column.")
            with archive.open(csv_name) as csv_file:
                counts = pd.read_csv(csv_file, usecols=CSV_COLUMNS + [period])
        edges = gpd.read_file(f"/vsizip/{path}/{shp_name}").to_crs(4326)

        if counts.empty:
            raise ValueError("The Strava file holds no count.")
        missing = set(counts["edge_uid"]).difference(edges["edgeUID"])
        if missing:
            raise ValueError(f"{len(missing)} edges of the CSV missing from the shapefile.")

        start = pd.to_datetime(counts[period].astype(str), format="%Y" if period == "year" else "%Y-%m-%d")
        start = start.dt.tz_localize("Europe/Paris")
        geometries = edges.set_index("edgeUID").geometry
        rows = pd.DataFrame(
            {
                "external_id": counts["edge_uid"].astype(str),
                "geometry": geometries.loc[counts["edge_uid"]].values,
                "start_datetime": start,
                "end_datetime": start + PERIODS[period],
                "count": counts["total_trip_count"],
                "activity": counts["activity_type"],
            }
        )
        return len(counts), rows
