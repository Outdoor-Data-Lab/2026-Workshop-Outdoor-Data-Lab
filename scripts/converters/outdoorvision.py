# /// script
# dependencies = ["geopandas", "pyogrio"]
# ///
"""Exports Outdoorvision (GPKG) -> CSV pivot. T = passages, U = pratiquants (en extra).
Usage : uv run outdoorvision.py <dossier_gpkg> <sortie.csv>"""
import json, re, sys
from pathlib import Path
import geopandas as gpd, pandas as pd

PRATIQUES = {"walking": "hiking", "running": "running", "cycling": "biking", "skiing": "skiing"}
NOM = re.compile(r"_(AA_)?[A-Za-z]+_(\d{8})_(\d{8})_([a-z]+)\.gpkg$")
iso = lambda d: f"{d[4:]}-{d[2:4]}-{d[:2]}"

def convert(f):
    aa, debut, fin, act = NOM.search(f.name).groups()
    g = gpd.read_file(f).to_crs(4326)
    return pd.DataFrame({
        "identifiant_source": "outdoorvision", "identifiant_objet": g["id segment"].astype(str),
        "nom_objet": "", "type_objet": "segment", "geom_wkt": g.geometry.to_wkt(rounding_precision=6),
        "date_debut": iso(debut), "date_fin": iso(fin), "denombrement": g["T"],
        "entite_comptee": "person", "pratique": PRATIQUES[act],
        "extra": [json.dumps({"U": int(u), "zone": "aire_adhesion" if aa else "coeur"}) for u in g["U"]],
    })

src, out = map(Path, sys.argv[1:3])
df = pd.concat(convert(f) for f in sorted(src.glob("*.gpkg")) if NOM.search(f.name))
df.drop_duplicates(["identifiant_objet", "pratique", "date_debut"]).to_csv(out, sep=";", index=False)
