"""Authorization generation, tied to the shared patient cohort and the real
payer-facility network rather than an independently sampled population.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import identifiers as ids

CPT_BY_SERVICE = {
    "pre_op": ("99213", "Established patient office visit – pre-operative clearance"),
    "infusion": ("96413", "Chemotherapy administration, IV infusion, first hour"),
    "radiation": ("77301", "Intensity-modulated radiotherapy planning"),
}

DENIAL_REASONS = [
    "Not medically necessary per payer guidelines",
    "Missing clinical documentation",
    "Out-of-network facility requested",
    "Prior authorization not obtained before service",
    "Alternative treatment not attempted first",
]

THIRD_PARTY_REVIEWERS = [
    "Meridian Utilization Management", "Northstar Clinical Review",
    "Alliance Utilization Management", "Precision Prior-Auth Partners",
    "Internal Payer UM Team",
]

REVIEWER_FIRST = ["Alex", "Jamie", "Morgan", "Taylor", "Casey", "Drew"]
REVIEWER_LAST = ["Turner", "Brooks", "Hayes", "Coleman", "Reyes", "Blake"]


def build_authorizations(
    rng: random.Random, patients: list[dict], milestone_facts: list[dict],
) -> list[dict]:
    """One authorization per patient's auth-gated pathway step (pre-op,
    infusion, or radiation), reflecting their assigned payer/plan/facility."""
    auth_gate_fact_by_patient: dict[str, dict] = {}
    for fact in milestone_facts:
        if fact["gate_type"] == "auth":
            auth_gate_fact_by_patient[fact["patient_id"]] = fact

    rows = []
    seq = 0
    for patient in patients:
        fact = auth_gate_fact_by_patient.get(patient["patient_id"])
        if fact is None:
            continue
        service_type = fact["service_type"]
        cpt_code, cpt_description = CPT_BY_SERVICE.get(service_type, ("99499", "Unlisted evaluation and management service"))
        seq += 1
        status = patient["insurance_auth_status"]
        request_date = datetime.strptime(patient["definitive_treatment_date"] or "2026-01-01", "%Y-%m-%d") \
            if patient["definitive_treatment_date"] else datetime(2026, 1, 1)
        request_date = request_date - timedelta(days=rng.randint(15, 35))
        decision_lag = rng.randint(1, 21) if status != "Pending" else None
        decision_date = (request_date + timedelta(days=decision_lag)) if decision_lag else None

        peer_to_peer = status == "Denied" or (status == "Pending" and rng.random() < 0.2)
        denial_reason = rng.choice(DENIAL_REASONS) if status == "Denied" else None

        rows.append({
            "auth_id": ids.authorization_id(seq),
            "patient_id": patient["patient_id"],
            "payer_id": patient["payer_id"],
            "plan_id": patient["plan_id"],
            "ordering_provider_id": patient["assigned_provider_id"],
            "facility_id": patient["facility_id"],
            "cpt_code": cpt_code,
            "cpt_description": cpt_description,
            "primary_dx_code": patient["primary_dx_code"],
            "auth_status": status,
            "authorization_code": ids.authorization_code(seq) if status == "Approved" else None,
            "validity_start": decision_date.strftime("%Y-%m-%d") if decision_date and status == "Approved" else None,
            "validity_end": (decision_date + timedelta(days=180)).strftime("%Y-%m-%d") if decision_date and status == "Approved" else None,
            "peer_to_peer_required": peer_to_peer,
            "third_party_reviewer": rng.choice(THIRD_PARTY_REVIEWERS),
            "reviewer_name": f"{rng.choice(REVIEWER_FIRST)} {rng.choice(REVIEWER_LAST)}",
            "num_clinical_questions_asked": rng.randint(2, 12),
            "total_time_spent_on_phone_min": rng.randint(5, 65),
            "denial_reason": denial_reason,
            "request_date": request_date.strftime("%Y-%m-%d"),
            "decision_date": decision_date.strftime("%Y-%m-%d") if decision_date else None,
        })
    return rows
