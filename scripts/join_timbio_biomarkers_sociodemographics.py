#!/usr/bin/env python3
"""Join Timbio biomarker records to matching sociodemographic records.

Raw workbooks are read-only. The output is a local derived dataset and an
audit table describing join coverage and unmatched biomarker records.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"

BIOMARKER_FILE = RAW / "BD Timbío Biomarcadores para Endoscopia  27-08.xlsx"
SOCIO_FILE = RAW / "BaseDatosConsolidad_469caracterización_HPylori_EcuenstaTamizadosv2.xlsx"
OUT_PARQUET = INTERIM / "biomarkers_timbio_with_sociodemographics_v2.parquet"
OUT_XLSX = INTERIM / "biomarkers_timbio_with_sociodemographics_v2.xlsx"
OUT_AUDIT = INTERIM / "biomarkers_timbio_sociodemographic_join_audit_v2.csv"

BIO_ID = "data-datos_ubicacion-identificador"
BIO_MUNICIPALITY = "data-datos_ubicacion-municipio"
SOCIO_SHEET = "Pacientes priorizados"
SOCIO_ID = "ID_Paciente"
SOCIO_MUNICIPALITY = "Nom.Municipio"


def normalize_id(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]", "", text) or None


def normalize_municipality(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def main() -> None:
    biomarker = pd.read_excel(BIOMARKER_FILE, sheet_name="Hoja 1")
    socio = pd.read_excel(SOCIO_FILE, sheet_name=SOCIO_SHEET)

    biomarker = biomarker.loc[
        biomarker[BIO_MUNICIPALITY].map(normalize_municipality).eq("TIMBIO")
    ].copy()
    socio = socio.loc[
        socio[SOCIO_MUNICIPALITY].map(normalize_municipality).eq("TIMBIO")
    ].copy()

    biomarker["patient_id_canonical"] = biomarker[BIO_ID].map(normalize_id)
    socio["patient_id_canonical"] = socio[SOCIO_ID].map(normalize_id)

    if biomarker["patient_id_canonical"].duplicated().any():
        raise ValueError("Biomarker IDs are not unique after normalization.")
    if socio["patient_id_canonical"].duplicated().any():
        raise ValueError("Sociodemographic IDs are not unique after normalization.")

    socio = socio.drop(columns=[SOCIO_ID], errors="ignore")
    overlapping = (set(biomarker.columns) & set(socio.columns)) - {"patient_id_canonical"}
    socio = socio.rename(columns={column: f"{column}__sociodemographic" for column in overlapping})

    joined = biomarker.merge(
        socio,
        on="patient_id_canonical",
        how="left",
        indicator="sociodemographic_join_status",
        validate="one_to_one",
        suffixes=("", "__sociodemographic"),
    )
    joined["sociodemographic_join_status"] = joined["sociodemographic_join_status"].map(
        {"both": "matched", "left_only": "biomarker_only"}
    )

    match_counts = joined["sociodemographic_join_status"].value_counts(dropna=False).to_dict()
    audit = pd.DataFrame(
        [
            {
                "source_biomarkers": BIOMARKER_FILE.name,
                "source_sociodemographics": SOCIO_FILE.name,
                "municipality_filter": "TIMBIO (accent-insensitive)",
                "biomarker_rows_timbio": len(biomarker),
                "sociodemographic_rows_timbio": len(socio),
                "matched_rows": int(match_counts.get("matched", 0)),
                "biomarker_only_rows": int(match_counts.get("biomarker_only", 0)),
                "sociodemographic_only_rows": max(len(socio) - int(match_counts.get("matched", 0)), 0),
                "biomarker_unique_ids": biomarker["patient_id_canonical"].nunique(),
                "sociodemographic_unique_ids": socio["patient_id_canonical"].nunique(),
                "id_missing_biomarkers": int(biomarker["patient_id_canonical"].isna().sum()),
                "id_missing_sociodemographics": int(socio["patient_id_canonical"].isna().sum()),
            }
        ]
    )

    INTERIM.mkdir(parents=True, exist_ok=True)
    joined.to_excel(OUT_XLSX, index=False)
    audit.to_csv(OUT_AUDIT, index=False)
    try:
        joined.to_parquet(OUT_PARQUET, index=False)
        parquet_status = f"Output parquet: {OUT_PARQUET}"
    except ImportError:
        parquet_status = "Parquet omitido: el entorno no tiene pyarrow ni fastparquet."
    print(audit.to_string(index=False))
    print(parquet_status)
    print(f"Output xlsx: {OUT_XLSX}")
    print(f"Audit: {OUT_AUDIT}")


if __name__ == "__main__":
    main()
