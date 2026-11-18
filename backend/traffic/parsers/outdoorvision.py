"""Import Outdoorvision raw tracks (GeoPackage) into the traffic application.

One GPKG line = one continuous piece of an outing. The pieces of a track_id are
merged: one outing = one counting object with one passage (count = 1).
"""

import geopandas as gpd
import pandas as pd
from pyogrio.errors import DataSourceError

from .base import TrafficParser

REQUIRED_COLUMNS = {"id", "track_id", "date_start", "date_end", "activity", "geometry"}


class OutdoorVisionParser(TrafficParser):
    NAME = "Outdoorvision"
    EXAMPLE = (
        "GPKG de traces brutes, un fichier à la fois. Ex. : Export_Traces_PNR_Vercors_12.gpkg "
        "(colonnes id, track_id, activity, date_start, date_end). Le .hdf livré à côté est inutile."
    )
    # Outdoorvision activity -> commons practice code (any level of the hierarchy).
    PRACTICE_CODES = {
        "walking": "walking",
        "hiking": "hiking",
        "running": "running",
        "cycling": "cycling",
        "biking": "cycling",
        "skiing": "skiing",
    }

    def read(self) -> tuple[int, pd.DataFrame]:
        with self.data_import.file.open("rb") as source_file:
            try:
                tracks = gpd.read_file(source_file)
            except DataSourceError as error:
                raise ValueError("Le fichier Outdoorvision n'est pas un GPKG lisible.") from error

        missing = REQUIRED_COLUMNS.difference(tracks.columns)
        if missing:
            raise ValueError(f"Colonnes Outdoorvision manquantes : {', '.join(sorted(missing))}")
        if tracks.crs is None:
            raise ValueError("Le fichier Outdoorvision ne définit aucun SCR.")
        if tracks.empty:
            raise ValueError("Le fichier Outdoorvision ne contient aucune donnée.")
        if tracks["track_id"].isna().any():
            raise ValueError("Certaines lignes Outdoorvision n'ont pas de track_id.")
        if tracks["activity"].isna().any():
            raise ValueError("Certaines lignes Outdoorvision n'ont pas d'activité.")
        if tracks.geometry.isna().any() or tracks.geometry.is_empty.any():
            raise ValueError("Certaines lignes Outdoorvision n'ont pas de géométrie.")
        for column in ("date_start", "date_end"):
            tracks[column] = pd.to_datetime(tracks[column], errors="coerce", utc=True)
            if tracks[column].isna().any():
                raise ValueError(f"Certaines valeurs de {column} ne sont pas des dates valides.")

        tracks["track_id"] = tracks["track_id"].astype(str)
        tracks["activity"] = tracks["activity"].astype(str).str.strip().str.lower()
        several = tracks.groupby("track_id")["activity"].nunique().loc[lambda n: n > 1]
        if not several.empty:
            raise ValueError(f"Plusieurs activités sont associées au track_id {several.index[0]}.")

        outings = tracks.to_crs(4326).dissolve(
            by="track_id", aggfunc={"date_start": "min", "date_end": "max", "activity": "first"}
        )
        backwards = outings.index[outings.date_end <= outings.date_start]
        if len(backwards):
            raise ValueError(f"La date de fin du track_id {backwards[0]} doit suivre sa date de début.")

        outings = outings.reset_index()
        rows = pd.DataFrame(
            {
                "external_id": outings.track_id,
                "geometry": outings.geometry,
                "start_datetime": outings.date_start,
                "end_datetime": outings.date_end,
                "count": 1,
                "activity": outings.activity,
            }
        )
        return len(tracks), rows
