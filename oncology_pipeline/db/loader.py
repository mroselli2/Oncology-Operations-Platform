"""Loads a freshly generated cohort (dict of table_name -> list[dict]) into
a SQLite database, rebuilt from scratch on every call.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def build_database(data: dict[str, list[dict]], db_path: Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_FILE.read_text())
        for table_name, rows in data.items():
            if not rows:
                continue
            schema_columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})")]
            df = pd.DataFrame(rows)
            df = df[[c for c in schema_columns if c in df.columns]]
            df.to_sql(table_name, conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()
