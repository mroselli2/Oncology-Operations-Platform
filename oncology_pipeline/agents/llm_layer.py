"""Bounded OpenRouter narrative layer on top of the deterministic agent
outputs. Selects up to `llm_max_cases` highest-risk patients plus one
cohort synthesis. On failure or budget exhaustion, a case's existing
deterministic template is left untouched -- rows are only upgraded on
verified success.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from ..llm import client as llm_client
from ..llm import fact_packet
from ..llm.budget import BudgetGuard


def run_llm_layer(conn: sqlite3.Connection, analysis_df: pd.DataFrame, settings, run_id: str) -> dict:
    ledger_path = settings.outputs_dir / "llm_usage_ledger.csv"

    if settings.llm_mode == "off":
        return {"attempted": False, "reason": "llm_mode_off"}

    budget = BudgetGuard(budget_usd=settings.llm_run_budget_usd, calls_capped_at=settings.llm_max_calls_per_run)

    active = analysis_df[analysis_df["scheduling_status"] != "Completed"]
    top_cases = active.sort_values("risk_score", ascending=False).head(settings.llm_max_cases)

    case_results = []
    for _, row in top_cases.iterrows():
        agent_output_row = {
            "risk_score": row["risk_score"], "risk_level": row["risk_level"],
            "primary_bottleneck": row["primary_bottleneck"], "missing_items": row["missing_items"],
            "recommended_action": row["recommended_action"], "projected_total_days": row["projected_total_days"],
        }
        packet = fact_packet.build_patient_fact_packet(conn, row["patient_id"], agent_output_row)
        result = llm_client.run_patient_case(
            conn, row["patient_id"], packet, agent_output_row, settings, budget, run_id,
            settings.cache_dir, ledger_path,
        )
        case_results.append((row["patient_id"], result))

        if result.status == "success":
            narrative = result.narrative
            conn.execute(
                """UPDATE agent_outputs SET narrative_source = 'openrouter_llm',
                   internal_draft_note = ?, recommended_action = ?
                   WHERE run_id = ? AND patient_id = ?""",
                (narrative["internal_coordinator_note"], narrative["recommended_next_action"], run_id, row["patient_id"]),
            )
            conn.execute(
                """INSERT INTO llm_case_narratives
                   (run_id, patient_id, operational_summary, primary_bottleneck, priority_rationale,
                    recommended_next_action, internal_coordinator_note, supporting_fact_ids,
                    uncertainty_statement, human_review_required, generated_by, model_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, row["patient_id"], narrative["operational_summary"], narrative["primary_bottleneck"],
                 narrative["priority_rationale"], narrative["recommended_next_action"],
                 narrative["internal_coordinator_note"], json.dumps(narrative["supporting_fact_ids"]),
                 narrative["uncertainty_statement"], 1, narrative["generated_by"], narrative["model_name"]),
            )
    conn.commit()

    cohort_packet = fact_packet.build_cohort_fact_packet(conn, analysis_df)
    cohort_result = llm_client.run_cohort_synthesis(conn, cohort_packet, settings, budget, run_id, settings.cache_dir, ledger_path)
    if cohort_result.status == "success":
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        (settings.outputs_dir / "cohort_synthesis.json").write_text(json.dumps(cohort_result.narrative, indent=2))

    return {
        "attempted": True,
        "cases_attempted": len(case_results),
        "cases_succeeded": sum(1 for _, r in case_results if r.status == "success"),
        "cohort_synthesis_status": cohort_result.status,
        "budget_spent_usd": budget.spent_usd,
        "calls_made": budget.calls_made,
    }
