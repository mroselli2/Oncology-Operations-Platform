"""Builds compact, structured fact packets from deterministic outputs --
never a raw table dump or the full cohort. Every fact is keyed by a stable
id the LLM must cite back in `supporting_fact_ids`; anything it cites that
isn't in `allowed_fact_ids` fails validation (see llm/schemas.py).
"""

from __future__ import annotations

import sqlite3

from ..generation.core import ALL_MILESTONE_FIELDS
from .schemas import SCHEMA_VERSION

# v2: added provider.allow_fallbacks and the served-model-mismatch guard
# (client.py _call_with_one_retry). Bumping this invalidates cache entries
# written under the old, unguarded logic. Bump again whenever request
# construction or response-trust logic materially changes.
PROMPT_VERSION = "v2"


def build_patient_fact_packet(conn: sqlite3.Connection, patient_id: str, agent_output_row: dict) -> dict:
    from ..db import queries

    patient = queries.get_patient_full(conn, patient_id)
    facts: dict[str, str] = {
        f"{patient_id}:diagnosis_type": patient["diagnosis_type"],
        f"{patient_id}:stage": patient["stage"],
        f"{patient_id}:pathway": patient["treatment_modality_pathway"],
        f"{patient_id}:priority_level": patient["priority_level"],
        f"{patient_id}:scheduling_status": patient["scheduling_status"],
        f"{patient_id}:authorization_status": patient["insurance_auth_status"],
        f"{patient_id}:payer_type": patient["payer_type"],
        f"{patient_id}:facility": patient["facility_name"] or "Unassigned",
        f"{patient_id}:coordinator": patient["assigned_coordinator_name"] or "Unassigned",
        f"{patient_id}:risk_score": str(agent_output_row["risk_score"]),
        f"{patient_id}:risk_level": agent_output_row["risk_level"],
        f"{patient_id}:primary_bottleneck": agent_output_row["primary_bottleneck"],
        f"{patient_id}:missing_items": agent_output_row["missing_items"],
        f"{patient_id}:deterministic_recommended_action": agent_output_row["recommended_action"],
        f"{patient_id}:projected_total_days": str(agent_output_row["projected_total_days"]),
    }
    for field_name in ALL_MILESTONE_FIELDS:
        val = patient.get(field_name)
        if val:
            facts[f"{patient_id}:{field_name}"] = val

    row = conn.execute(
        """SELECT candidate_facility_id, candidate_date, reason_code FROM slot_recommendations
           WHERE patient_id = ? ORDER BY rank ASC LIMIT 1""",
        (patient_id,),
    ).fetchone()
    if row:
        facts[f"{patient_id}:top_slot_recommendation"] = (
            f"{row['candidate_facility_id']} on {row['candidate_date']} ({row['reason_code']})"
        )

    return {
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "patient_id": patient_id,
        "facts": facts,
        "allowed_fact_ids": sorted(facts.keys()),
    }


def build_cohort_fact_packet(conn: sqlite3.Connection, analysis_df) -> dict:
    facts: dict[str, str] = {
        "COHORT:patient_count": str(len(analysis_df)),
        "COHORT:high_risk_count": str(int((analysis_df["risk_level"] == "High").sum())),
        "COHORT:moderate_risk_count": str(int((analysis_df["risk_level"] == "Moderate").sum())),
        "COHORT:delayed_count": str(int((analysis_df["scheduling_status"] == "Delayed").sum())),
    }
    top_bottlenecks = analysis_df["primary_bottleneck"].value_counts().head(5)
    for i, (bottleneck, count) in enumerate(top_bottlenecks.items(), start=1):
        facts[f"COHORT:top_bottleneck_{i}"] = f"{bottleneck} ({count} patients)"
    for i, (pathway, count) in enumerate(analysis_df["treatment_modality_pathway"].value_counts().items(), start=1):
        facts[f"COHORT:pathway_{i}"] = f"{pathway} ({count} patients)"

    return {
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "scope_id": "COHORT",
        "facts": facts,
        "allowed_fact_ids": sorted(facts.keys()),
    }
