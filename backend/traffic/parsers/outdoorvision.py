"""Import Outdoorvision GeoPackages into the traffic application."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from commons.models import DataImport, Practice

from ..models import (
    CountingMeasure,
    CountingObject,
    CountingObjectType,
    Unit,
)


# OutdoorVision activity -> commons practice code (any level of the hierarchy).
PRACTICE_CODES = {
    "walking": "walking",
    "hiking": "hiking",
    "running": "running",
    "cycling": "cycling",
    "biking": "cycling",
    "skiing": "skiing",
}
REQUIRED_COLUMNS = {
    "id",
    "track_id",
    "date_start",
    "date_end",
    "activity",
    "geometry",
}


class OutdoorVisionParser:
    """Parse one Outdoorvision import and persist its tracks and measures."""

    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.file = data_import.file
        self.name = Path(self.file.name).name

    def _read_tracks(self) -> gpd.GeoDataFrame:
        with self.file.open("rb") as source_file:
            tracks = gpd.read_file(source_file)

        missing_columns = REQUIRED_COLUMNS.difference(tracks.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Colonnes Outdoorvision manquantes : {missing}")
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
                raise ValueError(
                    f"Certaines valeurs de {column} ne sont pas des dates valides."
                )

        return tracks.to_crs(4326)

    def _aggregate_tracks(self, tracks: gpd.GeoDataFrame) -> list[dict]:
        aggregated_tracks = []
        for track_id, rows in tracks.groupby("track_id", sort=False):
            practice_codes = {
                PRACTICE_CODES.get(value, value)
                for value in rows["activity"].astype(str).str.strip().str.lower()
            }
            if len(practice_codes) != 1:
                raise ValueError(
                    f"Plusieurs activités sont associées au track_id {track_id}."
                )

            start_datetime = rows["date_start"].min().to_pydatetime()
            end_datetime = rows["date_end"].max().to_pydatetime()
            if end_datetime <= start_datetime:
                raise ValueError(
                    f"La date de fin du track_id {track_id} doit suivre sa date de début."
                )

            aggregated_tracks.append(
                {
                    "track_id": str(track_id),
                    "geometry": rows.geometry.union_all(),
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "practice_code": practice_codes.pop(),
                }
            )
        return aggregated_tracks

    def import_data(self) -> int:
        """Create or update traffic objects and measures; return the track count."""
        tracks = self._read_tracks()
        aggregated_tracks = self._aggregate_tracks(tracks)

        practice_codes = {track["practice_code"] for track in aggregated_tracks}
        practices = Practice.objects.in_bulk(practice_codes, field_name="code")
        unknown_practices = practice_codes.difference(practices)
        if unknown_practices:
            unknown = ", ".join(sorted(unknown_practices))
            raise ValueError(f"Activités Outdoorvision inconnues : {unknown}")
        object_type = CountingObjectType.objects.get(code="segment")
        unit = Unit.objects.get(code="person")

        imported_tracks = 0
        with transaction.atomic():
            for track in aggregated_tracks:
                counting_object, _ = CountingObject.objects.update_or_create(
                    source=self.data_import.source,
                    external_id=track["track_id"],
                    defaults={
                        "type": object_type,
                        "geom": GEOSGeometry(
                            memoryview(track["geometry"].wkb), srid=4326
                        ),
                    },
                )

                CountingMeasure.objects.update_or_create(
                    counting_object=counting_object,
                    start_datetime=track["start_datetime"],
                    end_datetime=track["end_datetime"],
                    practice=practices[track["practice_code"]],
                    defaults={"count": 1, "unit": unit},
                )
                imported_tracks += 1

            self.data_import.line_numbers = len(tracks)
            self.data_import.error_numbers = 0
            self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        return imported_tracks


# Kept temporarily for code importing the former class names.
OutdoorvisionParser = OutdoorVisionParser
