"""Import iNaturalist observers (not their observations) into the traffic application.

Two files are accepted, both zipped CSV:
- the export of the iNaturalist site (README.txt + observations-*.csv; the
  download is a zip even when its name ends in .csv);
- a GBIF download of iNaturalist observations (one tab-separated CSV).

Only the observers are kept: one observer on one day = one outing = one
passage (count = 1, the day in Europe/Paris), whose geometry gathers the points
of their observations that day. Species are not imported.

The geometry stays a multipoint, not a track: iNaturalist records no route, the
observations are few and often without a reliable time, so a line between them
would invent a path (across a slope, off the trails). Matching the points to the
trail network, if needed, belongs to the analysis, not to the import.

The observer is recognised by their name, the only identifier both files share
(GBIF recordedBy = the iNaturalist user name, or login when the user has no
name), so importing both files does not count an observer-day twice. The name is
not stored: the object's external id is a hash of the name and the day.

Obscured observations (moved at random within a cell of about 0.2°) cannot
locate the observer: they are skipped and counted in error_numbers. The
iNaturalist export flags them (coordinates_obscured); GBIF gives them a
coordinate uncertainty of at least 27 km.
"""

import hashlib
import io
import zipfile

import pandas as pd
import shapely

from .base import TrafficParser

# Format -> source column for each field read.
FORMATS = {
    "iNaturalist": {
        "name": "user_name",
        "login": "user_login",
        "day": "observed_on",
        "latitude": "latitude",
        "longitude": "longitude",
        "obscured": "coordinates_obscured",
    },
    "GBIF": {
        "name": "recordedBy",
        "day": "eventDate",
        "latitude": "decimalLatitude",
        "longitude": "decimalLongitude",
        "uncertainty": "coordinateUncertaintyInMeters",
    },
}
# GBIF coordinate uncertainty from which an observation is obscured (the
# smallest one of an obscured observation is 27 222 m).
OBSCURED_UNCERTAINTY = 27_000


class INaturalistParser(TrafficParser):
    NAME = "iNaturalist"
    CONTENT = (
        "Holds naturalist observations (points), of which only the observers are kept: "
        "an observer on a given day counts as one passage, located by the points of their observations "
        "of the day. These points are not joined into a track: the actual route is not known. "
        "Species are not imported."
    )
    EXAMPLE = (
        "Export from the iNaturalist site (zip holding observations-*.csv, even if its name ends with .csv) or "
        "GBIF download of the iNaturalist observations (zip, tab-separated CSV). E.g. "
        "iNaturalist-observations-816641.csv, GBIF-iNaturalist-0012597-261110092616502.zip. Importing both "
        "does not count the same observer twice on the same day."
    )
    # Observers are assumed on foot: the files do not say how they moved.
    PRACTICE_CODES = {"observation": "walking"}

    def read(self) -> tuple[int, pd.DataFrame]:
        format_name, lines = self._read_lines()
        columns = FORMATS[format_name]
        name = lines[columns["name"]].str.strip()
        if "login" in columns:  # a user without name appears by their login, as in GBIF
            name = name.where(name.fillna("") != "", lines[columns["login"]].str.strip())
        day = pd.to_datetime(lines[columns["day"]].str[:10], format="%Y-%m-%d", errors="coerce")
        latitude = pd.to_numeric(lines[columns["latitude"]], errors="coerce")
        longitude = pd.to_numeric(lines[columns["longitude"]], errors="coerce")
        if "obscured" in columns:
            obscured = lines[columns["obscured"]].str.lower() == "true"
        else:
            obscured = pd.to_numeric(lines[columns["uncertainty"]], errors="coerce") >= OBSCURED_UNCERTAINTY

        keep = ~obscured & name.fillna("").ne("") & day.notna() & latitude.notna() & longitude.notna()
        self.skipped_lines = int((~keep).sum())
        if not keep.any():
            raise ValueError(f"The {format_name} file holds no usable observation.")

        points = pd.DataFrame({"name": name, "day": day, "lat": latitude, "lon": longitude})[keep]
        # Sorted by outing: shapely builds the multipoints from consecutive points.
        points = points.drop_duplicates().sort_values(["name", "day"])
        outings = points.groupby(["name", "day"])
        geometries = shapely.multipoints(
            shapely.points(points["lon"], points["lat"]), indices=outings.ngroup().to_numpy()
        )
        keys = outings.size().index.to_frame(index=False)
        start = keys["day"].dt.tz_localize("Europe/Paris")
        rows = pd.DataFrame(
            {
                "external_id": [observer_day_id(n, d) for n, d in zip(keys["name"], keys["day"])],
                "geometry": geometries,
                "start_datetime": start,
                "end_datetime": start + pd.DateOffset(days=1),
                "count": 1,
                "activity": "observation",
            }
        )
        return len(lines), rows

    def _read_lines(self) -> tuple[str, pd.DataFrame]:
        """Open the CSV (zipped or not), recognise its format and read the columns used."""
        with self.data_import.file.open("rb") as source_file:
            data = source_file.read()
        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                csv_names = [
                    name for name in archive.namelist() if name.lower().endswith(".csv") and not name.startswith("__MACOSX/")
                ]
                if len(csv_names) != 1:
                    raise ValueError(f"The iNaturalist archive must hold a single .csv (found: {len(csv_names)}).")
                data = archive.read(csv_names[0])
        header = data[: data.find(b"\n")].decode("utf-8-sig", errors="replace")
        separator = "\t" if "\t" in header else ","
        found = set(pd.read_csv(io.BytesIO(data), sep=separator, nrows=0).columns)
        for format_name, columns in FORMATS.items():
            if set(columns.values()) <= found:
                lines = pd.read_csv(
                    io.BytesIO(data), sep=separator, usecols=list(columns.values()), dtype=str, low_memory=False
                )
                return format_name, lines
        expected = "; ".join(f"{name}: {', '.join(columns.values())}" for name, columns in FORMATS.items())
        raise ValueError(f"Unrecognised iNaturalist columns. Expected ({expected}).")


def observer_day_id(name: str, day: pd.Timestamp) -> str:
    """Id of an observer's day that does not reveal the observer."""
    return hashlib.sha256(f"{name}\n{day:%Y-%m-%d}".encode()).hexdigest()[:32]
