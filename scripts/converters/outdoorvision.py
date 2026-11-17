# /// script
# dependencies = ["geopandas", "pyogrio"]
# ///
"""Exports Outdoorvision (GPKG) -> CSV with the same columns as the parking and Strava parsers.
T (passages) -> count. Period and activity come from the file name, end date is exclusive.
Usage : uv run outdoorvision.py <dossier_gpkg> <sortie.csv>"""
import re, sys
from pathlib import Path
import geopandas as gpd, pandas as pd

ACTIVITIES = {"walking": "hiking", "running": "running", "cycling": "biking", "skiing": "skiing"}
NOM = re.compile(r"_[A-Za-z]+_(\d{8})_(\d{8})_([a-z]+)\.gpkg$")

def convert(f):
    debut, fin, act = NOM.search(f.name).groups()
    g = gpd.read_file(f).to_crs(4326)
    obj = g["id segment"].astype(str)
    return pd.DataFrame({
        "id_source": obj + f"_{act}_{debut}", "start_date": pd.to_datetime(debut, format="%d%m%Y"),
        "end_date": pd.to_datetime(fin, format="%d%m%Y") + pd.Timedelta(days=1),
        "count": g["T"], "object_name": None, "id_source_object": obj,
        "geom": g.geometry.to_wkt(rounding_precision=6), "type_geom": "linear", "activity": ACTIVITIES[act],
    })

src, out = map(Path, sys.argv[1:3])
df = pd.concat(convert(f) for f in sorted(src.glob("*.gpkg")) if NOM.search(f.name))
# Segments shared by the core and the adhesion area appear in both files.
df.drop_duplicates("id_source").to_csv(out, index=False)
