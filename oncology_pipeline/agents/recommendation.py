"""Recommendation Agent: produces a concrete next-action recommendation
from the deterministically computed bottleneck and risk."""

from __future__ import annotations

from typing import Any


def recommend(patient: dict[str, Any], intervals: dict, risk: dict) -> str:
    primary = intervals["primary_bottleneck"]
    level = risk["risk_level"]

    if patient["scheduling_status"] == "Completed":
        return "Journey complete – archive / outcomes tracking only."

    if "Pathology" in primary:
        return (
            "High priority: Contact outside facility / pathology lab to expedite report. "
            "Hold firm treatment start until received. Escalate if >7 days outstanding."
        )
    if "Biomarker" in primary:
        return (
            "Follow up with molecular pathology / reference lab on turnaround time. "
            "If not yet ordered, place order today — this gates treatment selection."
        )
    if "authorization denied" in primary.lower():
        return "Initiate formal appeal and request peer-to-peer review with medical director today."
    if "authorization" in primary.lower():
        return (
            "Follow up with insurance / financial counselor today. "
            "If pending >10 days, escalate to authorization specialist and consider peer-to-peer."
        )
    if "Imaging" in primary:
        return "Coordinate imaging completion; place order if missing and schedule ASAP."
    if "Tumor board" in primary:
        return "Add case to next available multidisciplinary tumor board slot; confirm required data is packaged in advance."
    if "Surgical discussion" in primary:
        return (
            "Review surgical discussion template availability for the assigned provider. "
            "Consider converting under-utilized return slots or using cancellation list for high-priority cases."
        )
    if "Radiation start delayed" in primary:
        return "Check linac scheduling capacity and simulation slot availability; escalate to radiation oncology charge therapist."
    if "no-shows" in primary:
        return f"Coordinate with {patient['assigned_coordinator_name']} on transportation support and proactive reminder calls; consider consolidating visits."
    if "overall projected" in primary:
        return "Escalate to service line leadership for capacity review across this diagnosis/pathway; consider cross-site scheduling."
    if level == "High":
        return (
            "Prioritize for daily huddle. Assign coordinator owner and set 48-hour follow-up. "
            "Evaluate whether a cancellation slot or template conversion can pull the case forward."
        )
    return (
        "Continue standard coordination. Re-check status in 5–7 days. "
        "Monitor for new barriers (auth, pathology, biomarker, clearance)."
    )
