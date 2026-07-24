"""Oncology Operations Explorer -- read-only dashboard over the published
snapshot. Makes no external calls, requires no secrets, and never writes to
the database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_PATH = REPO_ROOT / "published_data" / "oncology_operations_snapshot.db"
TODAY = "2026-07-23"

MILESTONE_LABELS = {
    "tumor_board_date": "Tumor Board Review",
    "surgical_discussion_date": "Surgical Discussion",
    "pre_op_clearance_date": "Pre-Op Clearance",
    "surgery_date": "Surgery",
    "neoadjuvant_start_date": "Neoadjuvant Therapy Start",
    "neoadjuvant_end_date": "Neoadjuvant Therapy End",
    "restaging_imaging_date": "Restaging Imaging",
    "radiation_planning_date": "Radiation Planning",
    "radiation_start_date": "Radiation Start",
    "radiation_end_date": "Radiation End",
    "reassessment_date": "Post-Treatment Reassessment",
    "systemic_therapy_start_date": "Systemic Therapy Start",
}

REASON_CODE_LABELS = {
    "PREREQUISITE_PENDING": "Waiting on prerequisites",
    "CANCELLATION_LIST": "Cancellation slot available",
    "IN_NETWORK_PREFERRED": "In-network facility",
    "NEXT_AVAILABLE": "Next available slot",
    "CLOSEST_FACILITY": "Closest facility",
}


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(SNAPSHOT_PATH)


@st.cache_data
def load_run_metadata() -> dict:
    conn = _connect()
    row = conn.execute("SELECT * FROM run_metadata LIMIT 1").fetchone()
    cols = [d[0] for d in conn.execute("SELECT * FROM run_metadata LIMIT 1").description]
    conn.close()
    return dict(zip(cols, row)) if row else {}


@st.cache_data
def load_patients_full() -> pd.DataFrame:
    conn = _connect()
    query = """
        SELECT p.*, ao.risk_score, ao.risk_level, ao.primary_bottleneck, ao.secondary_note,
               ao.missing_items, ao.recommended_action, ao.projected_total_days,
               ao.internal_draft_note, ao.narrative_source,
               r.referral_date, r.new_patient_visit_date,
               prov.full_name AS provider_name,
               coo.full_name AS coordinator_name,
               fac.name AS facility_name,
               pay.payer_name AS payer_name
        FROM patients p
        LEFT JOIN agent_outputs ao ON ao.patient_id = p.patient_id
        LEFT JOIN referrals r ON r.patient_id = p.patient_id
        LEFT JOIN providers prov ON prov.provider_id = p.assigned_provider_id
        LEFT JOIN coordinators coo ON coo.coordinator_id = p.assigned_coordinator_id
        LEFT JOIN facilities fac ON fac.facility_id = p.facility_id
        LEFT JOIN payers pay ON pay.payer_id = p.payer_id
    """
    df = pd.read_sql_query(query, conn)

    # First not-yet-scheduled step per patient, i.e. the current milestone.
    pending = pd.read_sql_query(
        """
        SELECT patient_id, field_name, barrier_reason FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY sequence_index) AS rn
            FROM pathway_milestones WHERE milestone_date IS NULL
        ) WHERE rn = 1
        """,
        conn,
    )
    conn.close()
    pending["current_milestone"] = pending["field_name"].map(MILESTONE_LABELS).fillna(pending["field_name"])
    df = df.merge(pending[["patient_id", "current_milestone", "barrier_reason"]], on="patient_id", how="left")
    df["current_milestone"] = df["current_milestone"].fillna("Fully scheduled")
    return df


@st.cache_data
def load_table(table_name: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df


@st.cache_data
def load_facility_network_summary() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        """
        SELECT f.name AS facility_name, f.facility_type, fc.service_type,
               fc.weekly_capacity, fc.avg_lead_time_days
        FROM facility_capabilities fc
        JOIN facilities f ON f.facility_id = fc.facility_id
        ORDER BY f.name, fc.service_type
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data
def load_payer_authorization_summary() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        """
        SELECT pay.payer_name, pay.payer_type, pl.plan_type, au.auth_status,
               COUNT(*) AS request_count,
               ROUND(AVG(au.total_time_spent_on_phone_min), 1) AS avg_phone_minutes
        FROM authorizations au
        JOIN payers pay ON pay.payer_id = au.payer_id
        LEFT JOIN payer_plans pl ON pl.plan_id = au.plan_id
        GROUP BY pay.payer_name, pl.plan_type, au.auth_status
        ORDER BY pay.payer_name, au.auth_status
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data
def load_in_network_coverage() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        """
        SELECT service_type,
               ROUND(100.0 * SUM(in_network) / COUNT(*), 1) AS pct_in_network
        FROM payer_facility_network
        GROUP BY service_type
        ORDER BY service_type
        """,
        conn,
    )
    conn.close()
    return df


SYNTHETIC_NOTICE = (
    "All patients, providers, payers, facilities, appointments, and identifiers "
    "shown in this application are synthetic."
)


def render_notice(container) -> None:
    container.markdown(
        f"""<div style="
            background-color: rgba(128,128,128,0.08);
            border-left: 3px solid rgba(128,128,128,0.35);
            border-radius: 4px;
            padding: 0.55rem 0.8rem;
            font-size: 0.85rem;
            line-height: 1.4;
            margin-bottom: 1rem;
        ">{SYNTHETIC_NOTICE}</div>""",
        unsafe_allow_html=True,
    )


def render_sidebar_metadata() -> None:
    meta = load_run_metadata()
    st.sidebar.markdown("### Snapshot")
    st.sidebar.markdown(
        f"- Scenario: `{meta.get('scenario_name', 'n/a')}`\n"
        f"- Random seed: `{meta.get('random_seed', 'n/a')}`\n"
        f"- Cohort size: `{meta.get('cohort_size', 'n/a')}`\n"
        f"- Dataset type: `{meta.get('dataset_type', 'synthetic')}`\n"
        f"- Pipeline version: `{meta.get('synthetic_data_version', 'n/a')}`\n"
        f"- Generated: `{str(meta.get('generated_at', 'n/a'))[:19]}`"
    )


def render_overview() -> None:
    st.header("Executive Overview")
    patients = load_patients_full()
    authorizations = load_table("authorizations")
    slots = load_table("slot_recommendations")

    total = len(patients)
    high = int((patients["risk_level"] == "High").sum())
    moderate = int((patients["risk_level"] == "Moderate").sum())
    low = int((patients["risk_level"] == "Low").sum())
    auth_backlog = int((authorizations["auth_status"] == "Pending").sum())
    incomplete_prereqs = int(
        (~patients["imaging_complete"].astype(bool) | ~patients["pathology_received"].astype(bool)
         | patients["biomarker_testing_status"].isin(["Pending", "Not Ordered"])).sum()
    )
    patients_with_slots = slots["patient_id"].nunique()
    facility_count = len(load_table("facilities"))
    coordinator_count = len(load_table("coordinators"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", total)
    c2.metric("High Risk", high)
    c3.metric("Moderate Risk", moderate)
    c4.metric("Low Risk", low)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Authorization Backlog", auth_backlog)
    c6.metric("Incomplete Prerequisites", incomplete_prereqs)
    c7.metric("Patients with Slot Recommendations", patients_with_slots)
    c8.metric("Facilities / Coordinators", f"{facility_count} / {coordinator_count}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Risk Distribution")
        st.bar_chart(patients["risk_level"].value_counts())
        st.subheader("Pathway Mix")
        st.bar_chart(patients["treatment_modality_pathway"].value_counts())
    with col2:
        st.subheader("Top Bottlenecks")
        st.bar_chart(patients["primary_bottleneck"].value_counts().head(8))
        st.subheader("Authorization Status")
        st.bar_chart(authorizations["auth_status"].value_counts())


def render_huddle_queue() -> None:
    st.header("Daily Huddle Queue")
    st.caption("Active, non-completed cases ranked by risk score. Read-only.")
    patients = load_patients_full()
    active = patients[patients["scheduling_status"] != "Completed"].copy()

    with st.expander("Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        risk_sel = f1.multiselect("Risk level", sorted(active["risk_level"].dropna().unique()))
        coordinator_sel = f2.multiselect("Coordinator", sorted(active["coordinator_name"].dropna().unique()))
        facility_sel = f3.multiselect("Facility", sorted(active["facility_name"].dropna().unique()))
        payer_sel = f4.multiselect("Payer", sorted(active["payer_name"].dropna().unique()))

        f5, f6, f7, f8 = st.columns(4)
        pathway_sel = f5.multiselect("Pathway", sorted(active["treatment_modality_pathway"].dropna().unique()))
        cancer_sel = f6.multiselect("Cancer type", sorted(active["diagnosis_type"].dropna().unique()))
        bottleneck_sel = f7.multiselect("Bottleneck", sorted(active["primary_bottleneck"].dropna().unique()))
        action_sel = f8.multiselect("Recommended action", sorted(active["recommended_action"].dropna().unique()))

    filtered = active
    for col, selection in [
        ("risk_level", risk_sel), ("coordinator_name", coordinator_sel),
        ("facility_name", facility_sel), ("payer_name", payer_sel),
        ("treatment_modality_pathway", pathway_sel), ("diagnosis_type", cancer_sel),
        ("primary_bottleneck", bottleneck_sel), ("recommended_action", action_sel),
    ]:
        if selection:
            filtered = filtered[filtered[col].isin(selection)]

    filtered = filtered.sort_values("risk_score", ascending=False)
    display_cols = {
        "mrn": "Patient ID", "risk_score": "Risk Score", "risk_level": "Risk Level",
        "treatment_modality_pathway": "Pathway", "current_milestone": "Current Milestone",
        "primary_bottleneck": "Primary Bottleneck", "insurance_auth_status": "Authorization Status",
        "coordinator_name": "Coordinator", "recommended_action": "Recommended Action",
    }
    view = filtered[list(display_cols.keys())].rename(columns=display_cols)

    st.caption(f"{len(view)} of {len(active)} active cases shown")
    st.dataframe(view, width="stretch", hide_index=True)

    st.download_button(
        "Download filtered queue (CSV)",
        data=view.to_csv(index=False),
        file_name="huddle_queue_filtered.csv",
        mime="text/csv",
    )


def render_patient_journey() -> None:
    st.header("Patient Journey Explorer")
    patients = load_patients_full()
    options = patients.sort_values("mrn")[["patient_id", "mrn", "diagnosis_type"]]
    labels = options.apply(lambda r: f"{r['mrn']} -- {r['diagnosis_type']}", axis=1)
    choice = st.selectbox("Select a patient", options=options["patient_id"], format_func=lambda pid: labels[options["patient_id"] == pid].iloc[0])

    row = patients[patients["patient_id"] == choice].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Risk Level", row["risk_level"])
    c1.metric("Risk Score", int(row["risk_score"]) if pd.notna(row["risk_score"]) else "n/a")
    c2.metric("Pathway", row["treatment_modality_pathway"])
    c2.metric("Stage", row["stage"])
    c3.metric("Status", row["scheduling_status"])
    c3.metric("Payer", row["payer_type"])

    st.subheader("Summary")
    st.write(
        f"**Diagnosis:** {row['diagnosis_type']} | **Priority:** {row['priority_level']} | "
        f"**Facility:** {row['facility_name']} | **Coordinator:** {row['coordinator_name']}"
    )
    st.write(f"**Referral date:** {row['referral_date']} | **New patient visit:** {row['new_patient_visit_date']}")
    st.write(f"**Primary bottleneck:** {row['primary_bottleneck']}")
    st.write(f"**Recommended action:** {row['recommended_action']}")

    st.subheader("Diagnostic Prerequisites")
    p1, p2, p3 = st.columns(3)
    p1.write(f"Imaging complete: {'Yes' if row['imaging_complete'] else 'No'}")
    p2.write(f"Pathology received: {'Yes' if row['pathology_received'] else 'No'}")
    p3.write(f"Biomarker testing: {row['biomarker_testing_status']}")

    st.subheader("Milestone Timeline")
    milestones = load_table("pathway_milestones")
    patient_milestones = milestones[milestones["patient_id"] == choice].sort_values("sequence_index")
    timeline_rows = []
    for _, m in patient_milestones.iterrows():
        label = MILESTONE_LABELS.get(m["field_name"], m["field_name"])
        has_date = pd.notna(m["milestone_date"])
        if has_date and m["milestone_date"] <= TODAY:
            status = "Completed"
        elif has_date:
            status = "Scheduled"
        elif pd.notna(m["barrier_reason"]):
            status = f"Blocked: {m['barrier_reason']}"
        else:
            status = "Not yet reached"
        timeline_rows.append({"Milestone": label, "Date": m["milestone_date"] if has_date else "--", "Status": status})
    st.dataframe(pd.DataFrame(timeline_rows), width="stretch", hide_index=True)

    st.subheader("Appointments and Encounters")
    a1, a2 = st.columns(2)
    with a1:
        st.caption("Appointments (planned or completed)")
        appts = load_table("appointments")
        patient_appts = appts[appts["patient_id"] == choice][["appointment_type_code", "scheduled_date", "status"]]
        st.dataframe(patient_appts.rename(columns={"appointment_type_code": "Type", "scheduled_date": "Date", "status": "Status"}),
                     width="stretch", hide_index=True)
    with a2:
        st.caption("Completed encounters")
        encounters = load_table("encounters")
        patient_enc = encounters[encounters["patient_id"] == choice][["encounter_type", "encounter_date", "notes_summary"]]
        st.dataframe(patient_enc.rename(columns={"encounter_type": "Type", "encounter_date": "Date", "notes_summary": "Notes"}),
                     width="stretch", hide_index=True)

    st.subheader("Authorization History")
    auths = load_table("authorizations")
    patient_auths = auths[auths["patient_id"] == choice][
        ["cpt_description", "auth_status", "request_date", "decision_date", "denial_reason"]
    ]
    st.dataframe(patient_auths.rename(columns={
        "cpt_description": "Service", "auth_status": "Status",
        "request_date": "Requested", "decision_date": "Decided", "denial_reason": "Denial Reason",
    }), width="stretch", hide_index=True)

    st.subheader("Portal Coordination Events")
    portal = load_table("portal_events")
    patient_portal = portal[portal["patient_id"] == choice][["event_type", "event_timestamp"]]
    st.dataframe(patient_portal.rename(columns={"event_type": "Event", "event_timestamp": "Date"}),
                 width="stretch", hide_index=True)

    st.subheader("Ranked Slot Recommendations")
    slots = load_table("slot_recommendations")
    facilities = load_table("facilities")
    patient_slots = slots[slots["patient_id"] == choice].merge(
        facilities[["facility_id", "name"]], left_on="candidate_facility_id", right_on="facility_id", how="left",
    ).sort_values("rank")
    if patient_slots.empty:
        st.write("No pending slot recommendations for this patient.")
    else:
        patient_slots["Reason"] = patient_slots["reason_code"].map(REASON_CODE_LABELS).fillna(patient_slots["reason_code"])
        view = patient_slots[["rank", "name", "candidate_date", "network_status", "distance_miles", "Reason"]]
        st.dataframe(view.rename(columns={
            "rank": "Rank", "name": "Facility", "candidate_date": "Candidate Date",
            "network_status": "Network Status", "distance_miles": "Distance (mi)",
        }), width="stretch", hide_index=True)


def render_operations() -> None:
    st.header("Operations and Capacity")
    patients = load_patients_full()

    st.subheader("Facility Capabilities and Lead Times")
    network = load_facility_network_summary()
    facility_filter = st.multiselect("Filter by facility", sorted(network["facility_name"].unique()))
    view = network[network["facility_name"].isin(facility_filter)] if facility_filter else network
    st.dataframe(view.rename(columns={
        "facility_name": "Facility", "facility_type": "Type", "service_type": "Service",
        "weekly_capacity": "Weekly Capacity", "avg_lead_time_days": "Avg Lead Time (days)",
    }), width="stretch", hide_index=True)

    st.subheader("Payer Authorization Volume and Turnaround")
    payer_auth = load_payer_authorization_summary()
    st.dataframe(payer_auth.rename(columns={
        "payer_name": "Payer", "payer_type": "Type", "plan_type": "Plan", "auth_status": "Status",
        "request_count": "Requests", "avg_phone_minutes": "Avg Phone Minutes",
    }), width="stretch", hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Coordinator Queue Volume")
        coordinator_load = patients.groupby("coordinator_name").agg(
            patient_count=("patient_id", "count"),
            avg_risk_score=("risk_score", "mean"),
            high_risk_count=("risk_level", lambda s: (s == "High").sum()),
        ).reset_index().sort_values("avg_risk_score", ascending=False)
        coordinator_load["avg_risk_score"] = coordinator_load["avg_risk_score"].round(1)
        st.dataframe(coordinator_load.rename(columns={
            "coordinator_name": "Coordinator", "patient_count": "Patients",
            "avg_risk_score": "Avg Risk Score", "high_risk_count": "High Risk Count",
        }), width="stretch", hide_index=True)

    with col2:
        st.subheader("In-Network Coverage by Service")
        st.dataframe(load_in_network_coverage().rename(columns={
            "service_type": "Service", "pct_in_network": "% In-Network",
        }), width="stretch", hide_index=True)

    st.subheader("Cancellation-Slot Utilization")
    slots = load_table("slot_recommendations")
    facilities = load_table("facilities")
    cancellations = slots[slots["cancellation_opening"] == 1].merge(
        facilities[["facility_id", "name"]], left_on="candidate_facility_id", right_on="facility_id", how="left",
    )
    cancellation_counts = cancellations.groupby("name").size().reset_index(name="Cancellation Slots").sort_values(
        "Cancellation Slots", ascending=False
    )
    st.dataframe(cancellation_counts.rename(columns={"name": "Facility"}), width="stretch", hide_index=True)

    st.subheader("Bottleneck Counts")
    st.bar_chart(patients["primary_bottleneck"].value_counts().head(10))


def main() -> None:
    st.set_page_config(page_title="Oncology Operations Explorer", layout="wide")

    if not SNAPSHOT_PATH.exists():
        st.error(
            f"Published snapshot not found at `{SNAPSHOT_PATH.relative_to(REPO_ROOT)}`. "
            "Run scripts/build_published_snapshot.py to generate it."
        )
        st.stop()

    st.title("Oncology Operations Explorer")
    st.caption("A read-only view of synthetic oncology access and care-coordination workflows.")
    render_notice(st)

    st.sidebar.title("Oncology Operations Explorer")
    render_notice(st.sidebar)
    render_sidebar_metadata()
    view = st.sidebar.radio(
        "View", ["Executive Overview", "Daily Huddle Queue", "Patient Journey Explorer", "Operations and Capacity"],
    )

    if view == "Executive Overview":
        render_overview()
    elif view == "Daily Huddle Queue":
        render_huddle_queue()
    elif view == "Patient Journey Explorer":
        render_patient_journey()
    else:
        render_operations()


if __name__ == "__main__":
    main()
