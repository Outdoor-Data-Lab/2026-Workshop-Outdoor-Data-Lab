"""Import SINP observation exports (GeoNature synthesis, ";"-separated CSV).

One line = one observation, identified by its permanent SINP uuid. Taxa are
given in TaxRef (cd_nom as cited, cd_ref as reference name).
"""

import pandas as pd

from .base import BiodiversityRecordParser

COLUMNS = {
    "id_perm_sinp": "uuid",
    "cd_ref": "cd_ref",
    "cd_nom": "original_id_taxon",
    "nom_valide": "scientific_name",
    "date_debut": "record_start_date",
    "date_fin": "record_end_date",
    "wkt_4326": "geom",
    "precision": "coordinate_uncertainty_in_meters",
    "jdd_uuid": "dataset_uuid",
}
REQUIRED = [
    "uuid",
    "original_id_taxon",
    "scientific_name",
    "record_start_date",
    "record_end_date",
    "geom",
]


class INPNParser(BiodiversityRecordParser):
    NAME = "INPN"
    CONTENT = (
        "Contient des observations d'espèces (une géométrie par observation, le plus souvent un point), "
        "avec leur taxon TaxRef."
    )
    EXAMPLE = (
        "CSV séparé par des points-virgules, export de la synthèse GeoNature (SINP), colonnes id_perm_sinp, "
        "cd_nom, cd_ref, nom_valide, date_debut, date_fin, wkt_4326, precision, jdd_uuid."
    )

    def read(self) -> tuple[int, pd.DataFrame]:
        with self.data_import.file.open("rb") as source_file:
            data = pd.read_csv(
                source_file,
                sep=";",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
                usecols=COLUMNS,
            )

        missing = set(COLUMNS).difference(data.columns)
        if missing:
            raise ValueError(f"Colonnes INPN manquantes : {', '.join(sorted(missing))}")
        if data.empty:
            raise ValueError("Le fichier INPN ne contient aucune observation.")

        rows = data.rename(columns=COLUMNS)
        incomplete = rows[REQUIRED].isna().any(axis=1)
        if incomplete.any():
            lines = ", ".join(str(i + 2) for i in rows.index[incomplete][:10])
            raise ValueError(f"Observations INPN incomplètes (lignes {lines}).")

        for column in ("record_start_date", "record_end_date"):
            rows[column] = pd.to_datetime(rows[column], format="ISO8601").dt.date
        for column in ("cd_ref", "coordinate_uncertainty_in_meters"):
            rows[column] = pd.to_numeric(rows[column]).astype("Int64")
        rows["referential"] = "taxref"
        return len(data), rows
