#!/usr/bin/env python3
"""Builds the committed, read-only dashboard snapshot from the deterministic
pipeline: baseline scenario, fixed seed, no LLM layer, no ledger, no cache.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from oncology_pipeline.agents.orchestrator import run_full_analysis
from oncology_pipeline.db.loader import build_database
from oncology_pipeline.db.queries import connect
from oncology_pipeline.generation.cohort import build_cohort

SNAPSHOT_PATH = Path(__file__).parent.parent / "published_data" / "oncology_operations_snapshot.db"
RUN_ID = "snapshot-v1"
TODAY = datetime(2026, 7, 23)


def main() -> None:
    data = build_cohort(scenario_name="baseline", cohort_size=1200, random_seed=42, run_id=RUN_ID)
    build_database(data, SNAPSHOT_PATH)

    conn = connect(SNAPSHOT_PATH)
    analysis_df = run_full_analysis(conn, TODAY, RUN_ID)
    conn.close()

    size_mb = SNAPSHOT_PATH.stat().st_size / (1024 * 1024)
    print(f"Snapshot written: {SNAPSHOT_PATH} ({size_mb:.1f} MB, {len(analysis_df)} patients)")


if __name__ == "__main__":
    main()
