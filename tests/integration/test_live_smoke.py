"""Live OpenRouter smoke test -- makes REAL API calls and incurs REAL cost.

Excluded from the default pytest run (pytest.ini: `addopts = -m "not live"`).
Run explicitly with `pytest -m live`, only with separate authorization from
the project owner -- see docs/responsible_use.md. Do not add to CI.

Scope: at most 2 live calls (1 patient case + 1 cohort synthesis), budget
capped at $0.05, default inexpensive model. Every attempted call is
recorded in outputs/llm_usage_ledger.csv regardless of outcome.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from oncology_pipeline.agents.llm_layer import run_llm_layer
from oncology_pipeline.agents.orchestrator import run_full_analysis
from oncology_pipeline.config import Settings
from oncology_pipeline.db.loader import build_database
from oncology_pipeline.db.queries import connect
from oncology_pipeline.generation.cohort import build_cohort

pytestmark = pytest.mark.live


@pytest.fixture
def small_cohort_db(tmp_path):
    data = build_cohort(scenario_name="baseline", cohort_size=20, run_id="run-live-smoke")
    db_path = tmp_path / "smoke.db"
    build_database(data, db_path)
    return db_path


def test_one_patient_case_and_one_cohort_synthesis(tmp_path, small_cohort_db):
    """At most 2 live calls. Verifies schema validation and, given the past
    incident, that the ledger's actual_model matches the configured model."""
    settings = Settings.from_env()
    settings.llm_mode = "on"
    settings.llm_max_cases = 1  # -> 1 patient call + 1 cohort synthesis = 2 total
    settings.llm_run_budget_usd = 0.05
    settings.llm_cache_enabled = False  # force a real call, not a cache hit
    settings.cache_dir = tmp_path / "cache"
    settings.outputs_dir = tmp_path / "outputs"

    conn = connect(small_cohort_db)
    today = datetime(2026, 7, 23)
    analysis_df = run_full_analysis(conn, today, "run-live-smoke")

    result = run_llm_layer(conn, analysis_df, settings, "run-live-smoke")

    assert result["attempted"] is True
    assert result["cases_attempted"] == 1
    assert result["calls_made"] <= 2
    assert result["budget_spent_usd"] <= 0.05

    import pandas as pd
    ledger = pd.read_csv(settings.outputs_dir / "llm_usage_ledger.csv")
    ledger = ledger[ledger["run_id"] == "run-live-smoke"]
    real_calls = ledger[ledger["cache_hit"] == False]  # noqa: E712
    assert len(real_calls) <= 2

    for _, row in real_calls[real_calls["success_or_fallback_status"] == "success"].iterrows():
        assert row["actual_model"] == settings.openrouter_model, (
            f"actual_model {row['actual_model']!r} != requested {settings.openrouter_model!r} "
            "-- this is the exact model-substitution failure mode from the 2026-07-23 incident"
        )
        assert row["schema_validation_status"] == "valid"

    conn.close()
