"""Typed read helpers over the SQLite DB, used by the agents and the LLM
fact-packet builder so they never write raw SQL themselves.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from ..generation.core import ALL_MILESTONE_FIELDS


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_patient_ids(conn: sqlite3.Connection) -> list[str]:
    return [r["patient_id"] for r in conn.execute("SELECT patient_id FROM patients")]


def get_patient_milestones_wide(conn: sqlite3.Connection, patient_id: str) -> dict[str, str | None]:
    """One column per milestone field, reconstructed from the normalized
    pathway_milestones table."""
    rows = conn.execute(
        "SELECT field_name, milestone_date FROM pathway_milestones WHERE patient_id = ?",
        (patient_id,),
    ).fetchall()
    wide = {field: None for field in ALL_MILESTONE_FIELDS}
    for row in rows:
        wide[row["field_name"]] = row["milestone_date"]
    return wide


_PATIENT_FULL_QUERY = """
    SELECT p.*, r.referral_date, r.new_patient_visit_date,
           prov.full_name AS assigned_provider_name,
           coo.full_name AS assigned_coordinator_name,
           fac.name AS facility_name,
           pay.payer_name AS payer_name
    FROM patients p
    LEFT JOIN referrals r ON r.patient_id = p.patient_id
    LEFT JOIN providers prov ON prov.provider_id = p.assigned_provider_id
    LEFT JOIN coordinators coo ON coo.coordinator_id = p.assigned_coordinator_id
    LEFT JOIN facilities fac ON fac.facility_id = p.facility_id
    LEFT JOIN payers pay ON pay.payer_id = p.payer_id
    WHERE p.patient_id = ?
"""


def get_patient_full(conn: sqlite3.Connection, patient_id: str) -> dict:
    """Patient row plus referral dates, joined display names, and wide
    milestone columns -- the row shape the agents expect."""
    patient = dict(conn.execute(_PATIENT_FULL_QUERY, (patient_id,)).fetchone())
    patient.update(get_patient_milestones_wide(conn, patient_id))
    return patient


def get_next_pending_step(conn: sqlite3.Connection, patient_id: str) -> dict | None:
    """The patient's earliest not-yet-scheduled pathway step -- feeds slot matching."""
    row = conn.execute(
        """SELECT * FROM pathway_milestones
           WHERE patient_id = ? AND milestone_date IS NULL
           ORDER BY sequence_index ASC LIMIT 1""",
        (patient_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_patients_full_df(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.DataFrame([get_patient_full(conn, pid) for pid in get_all_patient_ids(conn)])


def get_slot_candidates(conn: sqlite3.Connection, patient_id: str, service_type: str) -> pd.DataFrame:
    """Facilities offering `service_type`, with capacity/lead-time and this
    patient's network status -- the candidate pool for slot matching."""
    patient = dict(conn.execute("SELECT payer_id, plan_id, facility_id FROM patients WHERE patient_id = ?", (patient_id,)).fetchone())
    query = """
        SELECT f.facility_id, f.name, fc.weekly_capacity, fc.avg_lead_time_days,
               n.in_network
        FROM facility_capabilities fc
        JOIN facilities f ON f.facility_id = fc.facility_id
        LEFT JOIN payer_facility_network n
            ON n.facility_id = fc.facility_id
           AND n.service_type = fc.service_type
           AND n.payer_id = ? AND n.plan_id = ?
        WHERE fc.service_type = ?
    """
    return pd.read_sql_query(query, conn, params=(patient["payer_id"], patient["plan_id"], service_type))
