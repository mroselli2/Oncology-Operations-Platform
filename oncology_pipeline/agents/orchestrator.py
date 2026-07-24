"""Runs the deterministic agent pipeline over every patient, persists
results to agent_outputs + slot_recommendations, and returns a DataFrame
for the report layer. narrative_source is tracked per row so the LLM layer
can upgrade individual rows later without rewiring this function.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd

from ..db import queries
from . import bottleneck, communication, intake, recommendation, risk
from .slot_matching import run_slot_matching


def run_full_analysis(conn: sqlite3.Connection, today: datetime, run_id: str) -> pd.DataFrame:
    patient_ids = queries.get_all_patient_ids(conn)
    generated_at = datetime.now(timezone.utc).isoformat()
    results = []

    for patient_id in patient_ids:
        patient = queries.get_patient_full(conn, patient_id)
        flags = intake.review(patient)
        intervals = bottleneck.detect(patient, today)
        r = risk.score(patient, intervals)
        rec = recommendation.recommend(patient, intervals, r)
        note = communication.draft(patient, intervals, r, rec)

        results.append({
            **patient,
            "run_id": run_id,
            "generated_at": generated_at,
            "missing_items": "; ".join(flags) if flags else "None",
            "referral_to_npv_days": intervals["referral_to_npv_days"],
            "npv_to_next_step_days": intervals["npv_to_next_step_days"],
            "referral_to_definitive_days": intervals["referral_to_definitive_days"],
            "projected_total_days": intervals["projected_total_days"],
            "primary_bottleneck": intervals["primary_bottleneck"],
            "secondary_note": intervals["secondary_note"],
            "risk_score": r["risk_score"],
            "risk_level": r["risk_level"],
            "recommended_action": rec,
            "internal_draft_note": note,
            "narrative_source": "deterministic_template",
        })

    df = pd.DataFrame(results)

    agent_outputs_cols = [
        "run_id", "patient_id", "generated_at", "missing_items", "primary_bottleneck",
        "secondary_note", "risk_score", "risk_level", "projected_total_days",
        "recommended_action", "internal_draft_note", "narrative_source",
    ]
    df[agent_outputs_cols].to_sql("agent_outputs", conn, if_exists="append", index=False)

    patients = [queries.get_patient_full(conn, pid) for pid in patient_ids]
    slot_rows = run_slot_matching(conn, patients, today, run_id)
    if slot_rows:
        slot_df = pd.DataFrame(slot_rows)
        slot_df.to_sql("slot_recommendations", conn, if_exists="append", index=False)

    conn.commit()
    return df
