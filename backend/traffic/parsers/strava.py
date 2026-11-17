"""Import Strava Metro yearly exports into the traffic application.

One zip = one year: a shapefile of the edges network (edgeUID, geometry) and a
CSV with one line per edge used that year (total_trip_count = passages).
One used edge = one counting object with one yearly measure.
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .base import TrafficParser

CSV_COLUMNS = ["edge_uid", "activity_type", "year", "total_trip_count"]


class StravaParser(TrafficParser):
    NAME = "Strava"
    PRACTICE_CODES = {
        # TODO: inexact, "Run,Walk,Hike" mixes walking and running. Replace by a
        # practice grouping both (e.g. "pédestre") once it exists.
        "Run,Walk,Hike": "walking",
    }

    def read(self) -> tuple[int, pd.DataFrame]:
        path = Path(self.data_import.file.path)
        with zipfile.ZipFile(path) as archive:
            names = {Path(name).suffix.lower(): name for name in archive.namelist()}
            if not {".shp", ".csv"} <= names.keys():
                raise ValueError("L'archive Strava doit contenir un .shp et un .csv.")
            with archive.open(names[".csv"]) as csv_file:
                counts = pd.read_csv(csv_file, usecols=CSV_COLUMNS)
        edges = gpd.read_file(f"/vsizip/{path}/{names['.shp']}").to_crs(4326)

        if counts.empty:
            raise ValueError("Le fichier Strava ne contient aucun comptage.")
        if counts["year"].nunique() != 1:
            raise ValueError("Une archive Strava doit couvrir une seule année.")
        missing = set(counts["edge_uid"]).difference(edges["edgeUID"])
        if missing:
            raise ValueError(f"{len(missing)} tronçons du CSV absents du shapefile.")

        start = pd.Timestamp(year=int(counts["year"].iloc[0]), month=1, day=1, tz="UTC")
        geometries = edges.set_index("edgeUID").geometry
        rows = pd.DataFrame(
            {
                "external_id": counts["edge_uid"].astype(str),
                "geometry": geometries.loc[counts["edge_uid"]].values,
                "start_datetime": start,
                "end_datetime": start + pd.DateOffset(years=1),
                "count": counts["total_trip_count"],
                "activity": counts["activity_type"],
            }
        )
        return len(counts), rows
