"""Standalone script, not an import parser: merges the raw hourly counter CSVs
(wide format) into the long CSV imported by compteur.py (CompteurParser)."""

import argparse
from pathlib import Path

import pandas as pd
from shapely import Point


def parse_file(path: Path) -> pd.DataFrame:
    """Lit un CSV horaire (format large) et le passe en format long."""
    df = pd.read_csv(path, skiprows=[0, 1], parse_dates=["Temps"])
    df.fillna(0, inplace=True)
    return df.melt(
        id_vars="Temps",
        var_name="object_name",
        value_name="count",
    ).rename(columns={"Temps": "date_debut"})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge hourly counter CSVs into a single long-format file."
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Hourly CSVs (e.g. 2024_tous-sites.csv 2025_tous-sites.csv 2026_tous-sites.csv)",
    )
    parser.add_argument(
        "--gps",
        type=Path,
        default=Path("compteurs_gps.csv"),
        help="CSV of the coordinates (object_name, lat, lon). Default: compteurs_gps.csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("compteurs_long.csv"),
        help="Output CSV. Default: compteurs_long.csv",
    )
    args = parser.parse_args()

    df_long = pd.concat([parse_file(f) for f in args.files], ignore_index=True)

    gps_coord = pd.read_csv(args.gps).dropna(subset=["lat", "lon"])
    # object_name -> Point(lon, lat); sites without GPS give None
    points = {
        row.object_name: Point(row.lon, row.lat) for row in gps_coord.itertuples()
    }
    df_long["geom"] = df_long.object_name.map(points)

    df_long["id_source"] = "Eco_Compteur_PNE"
    df_long["type"] = "point"
    df_long["activity"] = "hiking"
    df_long["id_source_objet"] = df_long["object_name"]

    df_long = df_long.sort_values(["object_name", "date_debut"]).reset_index(drop=True)
    df_long["geom"] = df_long["geom"].map(lambda g: g.wkt if pd.notna(g) else None)
    df_long.to_csv(args.output, index=False)
    print(f"{len(df_long)} lines written to {args.output}")


if __name__ == "__main__":
    main()
