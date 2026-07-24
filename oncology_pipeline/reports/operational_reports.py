"""Operational reports: daily huddle queue, portal activity, facility
network, payer authorization, and coordinator workload -- CSV + one
combined Markdown summary, in addition to the main analysis workbook/report.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

HUDDLE_TOP_N = 30


def build_huddle_queue(analysis_df: pd.DataFrame) -> pd.DataFrame:
    active = analysis_df[analysis_df["scheduling_status"] != "Completed"]
    cols = ["mrn", "first_name", "last_name", "diagnosis_type", "treatment_modality_pathway",
            "risk_level", "risk_score", "primary_bottleneck", "recommended_action", "assigned_coordinator_name"]
    return active.sort_values("risk_score", ascending=False)[cols].head(HUDDLE_TOP_N)


def build_portal_activity(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT event_type, COUNT(*) AS event_count FROM portal_events GROUP BY event_type ORDER BY event_count DESC",
        conn,
    )


def build_facility_network_report(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT f.name AS facility_name, f.facility_type, fc.service_type,
                  fc.weekly_capacity, fc.avg_lead_time_days,
                  COUNT(a.appointment_id) AS scheduled_appointments
           FROM facility_capabilities fc
           JOIN facilities f ON f.facility_id = fc.facility_id
           LEFT JOIN appointments a ON a.facility_id = fc.facility_id
           GROUP BY f.facility_id, fc.service_type
           ORDER BY f.name, fc.service_type""",
        conn,
    )


def build_payer_authorization_report(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT p.payer_name, p.payer_type, au.auth_status, COUNT(*) AS count,
                  ROUND(AVG(au.total_time_spent_on_phone_min), 1) AS avg_phone_minutes
           FROM authorizations au
           JOIN payers p ON p.payer_id = au.payer_id
           GROUP BY p.payer_name, au.auth_status
           ORDER BY p.payer_name, au.auth_status""",
        conn,
    )


def build_coordinator_workload_report(analysis_df: pd.DataFrame) -> pd.DataFrame:
    g = analysis_df.groupby("assigned_coordinator_name").agg(
        patient_count=("mrn", "count"),
        avg_risk_score=("risk_score", "mean"),
        high_risk_count=("risk_level", lambda s: (s == "High").sum()),
        delayed_count=("scheduling_status", lambda s: (s == "Delayed").sum()),
    ).reset_index().sort_values("avg_risk_score", ascending=False)
    g["avg_risk_score"] = g["avg_risk_score"].round(1)
    return g


def write_operational_reports(conn: sqlite3.Connection, analysis_df: pd.DataFrame, outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    huddle = build_huddle_queue(analysis_df)
    portal = build_portal_activity(conn)
    network = build_facility_network_report(conn)
    payer_auth = build_payer_authorization_report(conn)
    coordinator = build_coordinator_workload_report(analysis_df)

    huddle.to_csv(outputs_dir / "huddle_queue.csv", index=False)
    portal.to_csv(outputs_dir / "portal_activity_report.csv", index=False)
    network.to_csv(outputs_dir / "facility_network_report.csv", index=False)
    payer_auth.to_csv(outputs_dir / "payer_authorization_report.csv", index=False)
    coordinator.to_csv(outputs_dir / "coordinator_workload_report.csv", index=False)

    lines = ["# Operational Reports", ""]
    for title, df in [
        ("Daily Huddle Queue (top risk, active cases)", huddle),
        ("Portal Activity", portal),
        ("Facility Network Capacity", network),
        ("Payer Authorization Summary", payer_auth),
        ("Coordinator Workload", coordinator),
    ]:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(df.to_markdown(index=False))
        lines.append("")
    (outputs_dir / "operational_reports.md").write_text("\n".join(lines), encoding="utf-8")
