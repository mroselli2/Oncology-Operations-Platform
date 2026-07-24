"""Loads the versioned, offline disease-reference taxonomy mapping.

Codes are only ever real, verifiable public taxonomy values (ICD-10-CM) or
explicitly null/`not_mapped` — never invented to look plausible. See
reference_data/disease_reference_v1.csv for the source-of-truth mapping and
its provenance notes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REFERENCE_DATA_DIR = Path(__file__).parent.parent / "reference_data"
DISEASE_REFERENCE_FILE = REFERENCE_DATA_DIR / "disease_reference_v1.csv"


def load_disease_reference() -> pd.DataFrame:
    return pd.read_csv(DISEASE_REFERENCE_FILE, dtype=str).fillna("")


def disease_reference_lookup() -> dict[str, dict]:
    """cancer_type -> {icd10_code, mapping_status, disease_ref_id, ...}"""
    df = load_disease_reference()
    return {row["cancer_type"]: row.to_dict() for _, row in df.iterrows()}
