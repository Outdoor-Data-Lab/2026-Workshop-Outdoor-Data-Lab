"""Parser for hourly parking counter 

Try : 
uv run python backend/workshop2026/parsers/parking_counter.py backend/workshop2026/data/rapportT6_01_June_2025_0050204011-0_PMC.csv \
  --id-object 0050204011-0 --name "Parking PMC" --geom "POINT(6.12 45.89)" -o out.csv
"""

import argparse
from pathlib import Path

import pandas as pd

OUTPUT_COLUMNS = [
    "id_source",
    "start_date",
    "end_date",
    "count",
    "object_name",
    "id_source_object",
    "geom",
    "type_geom",
    "activity",
]


def parse_parking_counter(
    path: str | Path,
    *,
    id_source_object: str,
    object_name: str,
    geom: str,
    activity: str = "parking",
    type_geom: str = "équipement",
) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", dtype=str)
    date_col = raw.columns[0]
    hour_cols = [c for c in raw.columns if c.startswith("H") and c[1:].isdigit()]

    days = raw[raw[date_col].str.fullmatch(r"\d{2}/\d{2}/\d{4}", na=False)]
    df = days.melt(
        id_vars=date_col, value_vars=hour_cols, var_name="hour", value_name="raw"
    )

    # Strip the "(*)" / "(M)" annotations
    df["count"] = pd.to_numeric(df["raw"].str.extract(r"^\s*(\d+)")[0]).astype("Int64")
    df = df.dropna(subset=["count"])
    day = pd.to_datetime(df[date_col], format="%d/%m/%Y")
    hour = df["hour"].str[1:].astype(int)
    start = day + pd.to_timedelta(hour - 1, unit="h")
    df["start_date"] = start
    df["end_date"] = start + pd.Timedelta(hours=1)

    df = df.sort_values("start_date").reset_index(drop=True)
    df["id_source"] = id_source_object + "_" + df["start_date"].dt.strftime("%Y%m%dT%H")
    df["object_name"] = object_name
    df["id_source_object"] = id_source_object
    df["geom"] = geom
    df["type_geom"] = type_geom
    df["activity"] = activity
    print(df)
    return df[OUTPUT_COLUMNS]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--id-object", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--geom", required=True, help="WKT, e.g. 'POINT(6.12 45.89)'")
    parser.add_argument("--activity", default="parking")
    parser.add_argument("--type-geom", default="équipement")
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    result = parse_parking_counter(
        args.csv,
        id_source_object=args.id_object,
        object_name=args.name,
        geom=args.geom,
        activity=args.activity,
        type_geom=args.type_geom,
    )
    if args.output:
        result.to_csv(args.output, index=False)
    else:
        print(result.to_string(max_rows=20))
