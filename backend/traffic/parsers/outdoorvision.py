"""Import Outdoorvision raw tracks (GeoPackage) into the traffic application.

One GPKG line = one continuous piece of an outing. The pieces of a track_id are
merged: one outing = one counting object with one passage (count = 1).

A raw track weighs tens of kB: a whole export takes gigabytes once read. The file
is therefore read by batches of about BATCH_LINES lines, each holding whole tracks.
"""

import geopandas as gpd
import pandas as pd
import pyogrio
from pyogrio.errors import DataSourceError

from .base import TrafficParser

REQUIRED_COLUMNS = {"id", "track_id", "date_start", "date_end", "activity", "geometry"}
BATCH_LINES = 2000


class OutdoorVisionParser(TrafficParser):
    LABEL = "OutdoorVision raw tracks (GPKG)"
    NAME = "Outdoorvision"
    CONTENT = (
        "Holds GPS tracks of outings (lines): the pieces of the same outing (track_id) "
        "are merged, and each outing counts as one passage."
    )
    EXAMPLE = (
        "GPKG of raw tracks, one file at a time. E.g. Export_Traces_PNR_Vercors_12.gpkg "
        "(columns id, track_id, activity, date_start, date_end, and provider if any: Openrunner, "
        "IGN..., kept as the origin of each track). The .hdf delivered with it is not needed."
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
        return self._read_tracks(self._checked_path())

    def read_batches(self):
        path = self._checked_path()
        keys = pyogrio.read_dataframe(path, columns=["track_id"], read_geometry=False, fid_as_index=True)
        if keys["track_id"].isna().any():
            raise ValueError("Some Outdoorvision lines have no track_id.")
        # Batch of each track: lines of the tracks before it, by BATCH_LINES.
        lines = keys.groupby("track_id").size()
        batches = lines.cumsum().shift(fill_value=0) // BATCH_LINES
        for fids in keys.index.groupby(keys["track_id"].map(batches)).values():
            yield self._read_tracks(path, fids)

    def _checked_path(self) -> str:
        """Path of the file, once checked to hold the expected columns."""
        path = self.data_import.file.path
        try:
            info = pyogrio.read_info(path)
        except DataSourceError as error:
            raise ValueError("The Outdoorvision file is not a readable GPKG.") from error
        columns = set(info["fields"]) | ({"geometry"} if info["geometry_type"] else set())
        missing = REQUIRED_COLUMNS.difference(columns)
        if missing:
            raise ValueError(f"Missing Outdoorvision columns: {', '.join(sorted(missing))}")
        if info["crs"] is None:
            raise ValueError("The Outdoorvision file defines no coordinate reference system.")
        if not info["features"]:
            raise ValueError("The Outdoorvision file holds no data.")
        return path

    def _read_tracks(self, path, fids=None) -> tuple[int, pd.DataFrame]:
        """The outings of the given lines (all by default)."""
        tracks = gpd.read_file(path, fids=fids)
        if tracks["track_id"].isna().any():
            raise ValueError("Some Outdoorvision lines have no track_id.")
        if tracks["activity"].isna().any():
            raise ValueError("Some Outdoorvision lines have no activity.")
        if tracks.geometry.isna().any() or tracks.geometry.is_empty.any():
            raise ValueError("Some Outdoorvision lines have no geometry.")
        for column in ("date_start", "date_end"):
            tracks[column] = pd.to_datetime(tracks[column], errors="coerce", utc=True)
            if tracks[column].isna().any():
                raise ValueError(f"Some {column} values are not valid dates.")

        tracks["track_id"] = tracks["track_id"].astype(str)
        tracks["activity"] = tracks["activity"].astype(str).str.strip().str.lower()
        several = tracks.groupby("track_id")["activity"].nunique().loc[lambda n: n > 1]
        if not several.empty:
            raise ValueError(f"Several activities are given for track_id {several.index[0]}.")

        aggregates = {"date_start": "min", "date_end": "max", "activity": "first"}
        if "provider" in tracks:  # the application that recorded the track: its origin
            # As text: a column with no value at all is read as numbers.
            tracks["provider"] = tracks["provider"].astype("string").str.strip().replace("", None)
            aggregates["provider"] = "first"
        tracks = tracks.to_crs(4326)
        # Only the tracks in several pieces are merged: most have a single one, and
        # merging is by far the slowest step.
        pieces = tracks["track_id"].duplicated(keep=False)
        outings = pd.concat(
            [
                tracks[~pieces].set_index("track_id")[[*aggregates, "geometry"]],
                tracks[pieces].dissolve(by="track_id", aggfunc=aggregates),
            ]
        )
        backwards = outings.index[outings.date_end <= outings.date_start]
        if len(backwards):
            raise ValueError(f"The end date of track_id {backwards[0]} must follow its start date.")

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
        if "provider" in outings:
            rows["origin"] = outings.provider
        return len(tracks), rows
