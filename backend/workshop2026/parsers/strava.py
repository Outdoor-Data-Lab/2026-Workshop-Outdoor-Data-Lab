import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pandas import DataFrame


def find_member(names: list[str], extension: str) -> str:
    """
    From the list of file name in a zip archive, find the unique file with the given extension.

    :param names: A list of file names in a zip archive.
    :param extension: The file extension to search for.

    :return: The name of the unique file with the given extension.
    """
    matches = [
        n for n in names
        if Path(n).suffix.lower() == extension
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected only one file with extension {extension} in archive, found {len(matches)} : {matches}"
        )
    return matches[0]

def load_from_zip(zip_path: Path) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """
    Load data from a zip archive created by strava.

    :param zip_path: Path to the zip archive.
    :return: A tuple containing a GeoDataFrame (correspond to shp) and a DataFrame (correspond to csv).
    """
    with zipfile.ZipFile(zip_path) as zip_archive:
        names = zip_archive.namelist()
        csv_member = find_member(names, ".csv")
        shp_member = find_member(names, ".shp")

        with zip_archive.open(csv_member) as file:
            csv_df = pd.read_csv(file)

    shp_df = gpd.read_file(f"/vsizip/{zip_path.resolve().as_posix()}/{shp_member}")
    return shp_df, csv_df

def load_strava(zip_file: str | Path) -> DataFrame:
    """

    :param zip_file:
    :return:
    """
    zip_path = Path(zip_file)
    strava_shp, strava_csv = load_from_zip(zip_path)

    strava_shp["osmId"] = strava_shp["osmId"].astype("int64")
    strava_csv["osm_reference_id"] = strava_csv["osm_reference_id"].astype("int64")

    strava_full = strava_shp.merge(
        strava_csv,
        left_on="osmId",
        right_on="osm_reference_id",
        how="inner",
    )

    dates = pd.to_datetime(strava_full["date"])

    export = pd.DataFrame({
        "id_source": "Strava",
        "start_date": dates,
        "end_date": dates,
        "count": strava_full["total_trip_count"].astype("int64"),
        "object_name": None,
        "id_source_object": None,
        "geom": strava_full.geometry.to_wkt(),
        "type_geom": "Linear",
        "activity": strava_full["activity_type"],
    })

    return export

if __name__ == "__main__":
    zip_path = Path(sys.argv[1])
    strava_data_frame = load_strava(zip_path)
    export_path = zip_path.with_name(f"{zip_path.stem}_export.csv")
    strava_data_frame.to_csv(export_path, index=False)
    print(f"Export done in : {export_path}")
