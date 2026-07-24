"""Deterministic Slot-Matching Agent.

For each patient's earliest not-yet-scheduled pathway step, ranks candidate
facilities by prerequisite/authorization readiness, network status, lead
time, and distance. Entirely deterministic; the LLM layer may only narrate
these results, never compute or alter them.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

import pandas as pd

from .. import identifiers as ids
from ..db import queries

NETWORK_STATUS = {True: "In-Network", False: "Out-of-Network", None: "Not Applicable"}
TOP_N = 3


def _business_day(d: datetime) -> datetime:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _pseudo_distance(patient_id: str, facility_id: str) -> float:
    """Stable synthetic distance for a patient/facility pair (no real geocoding)."""
    h = hashlib.sha256(f"{patient_id}:{facility_id}".encode()).hexdigest()
    return round(2 + (int(h[:8], 16) % 5800) / 100, 1)  # 2.0 - 60.0 miles


def _cancellation_opening(rng: random.Random) -> bool:
    return rng.random() < 0.12


def match_slots_for_patient(conn, patient: dict, today: datetime, run_id: str, seq_start: int) -> tuple[list[dict], int]:
    step = queries.get_next_pending_step(conn, patient["patient_id"])
    if step is None:
        return [], seq_start

    candidates = queries.get_slot_candidates(conn, patient["patient_id"], step["service_type"])
    if candidates.empty:
        return [], seq_start

    prerequisites_met = step["barrier_reason"] is None
    authorization_status = patient["insurance_auth_status"] if step["gate_type"] == "auth" else "Not Required"

    rng = random.Random(int(hashlib.sha256(patient["patient_id"].encode()).hexdigest()[:8], 16))
    rows = []
    for _, cand in candidates.iterrows():
        network_tier = {True: 0, None: 1, False: 2}[cand["in_network"] if pd.notna(cand["in_network"]) else None]
        cancellation = _cancellation_opening(rng)
        lead_time = int(cand["avg_lead_time_days"])
        candidate_date = _business_day(today + timedelta(days=max(1, lead_time - (5 if cancellation else 0))))
        rows.append({
            "facility_id": cand["facility_id"],
            "network_tier": network_tier,
            "in_network": cand["in_network"] if pd.notna(cand["in_network"]) else None,
            "avg_lead_time_days": lead_time,
            "distance_miles": _pseudo_distance(patient["patient_id"], cand["facility_id"]),
            "cancellation_opening": cancellation,
            "candidate_date": candidate_date,
        })

    rows.sort(key=lambda r: (r["network_tier"], r["avg_lead_time_days"], r["distance_miles"]))
    top = rows[:TOP_N]
    min_lead_time = min(r["avg_lead_time_days"] for r in top)

    results = []
    seq = seq_start
    for rank, cand in enumerate(top, start=1):
        if not prerequisites_met:
            reason_code = "PREREQUISITE_PENDING"
        elif cand["cancellation_opening"]:
            reason_code = "CANCELLATION_LIST"
        elif cand["in_network"] is True:
            reason_code = "IN_NETWORK_PREFERRED"
        elif cand["avg_lead_time_days"] == min_lead_time:
            reason_code = "NEXT_AVAILABLE"
        else:
            reason_code = "CLOSEST_FACILITY"

        seq += 1
        results.append({
            "slot_recommendation_id": ids.slot_recommendation_id(seq),
            "run_id": run_id,
            "patient_id": patient["patient_id"],
            "appointment_type_code": step["service_type"],
            "rank": rank,
            "candidate_facility_id": cand["facility_id"],
            "candidate_provider_id": None,
            "candidate_date": cand["candidate_date"].strftime("%Y-%m-%d"),
            "prerequisites_met": prerequisites_met,
            "authorization_status": authorization_status,
            "network_status": NETWORK_STATUS[cand["in_network"]],
            "distance_miles": cand["distance_miles"],
            "cancellation_opening": cand["cancellation_opening"],
            "reason_code": reason_code,
        })
    return results, seq


def run_slot_matching(conn, patients: list[dict], today: datetime, run_id: str) -> list[dict]:
    all_rows = []
    seq = 0
    for patient in patients:
        rows, seq = match_slots_for_patient(conn, patient, today, run_id, seq)
        all_rows.extend(rows)
    return all_rows
