"""Bottleneck Detection Agent: computes interval lengths and names the
primary delay driver for a patient's pathway."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..generation.core import PATHWAY_STEPS


def _parse(val) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.strptime(str(val)[:10], "%Y-%m-%d")


def _days_between(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    return (b - a).days


def _milestone_order(pathway: str) -> list[str]:
    return [name for name, *_ in PATHWAY_STEPS[pathway]]


def detect(patient: dict[str, Any], today: datetime) -> dict[str, Any]:
    referral = _parse(patient["referral_date"])
    npv = _parse(patient["new_patient_visit_date"])
    pathway = patient["treatment_modality_pathway"]
    definitive_date = _parse(patient["definitive_treatment_date"])

    intervals: dict[str, Any] = {
        "referral_to_npv_days": _days_between(referral, npv),
        "referral_to_definitive_days": _days_between(referral, definitive_date),
    }

    milestone_fields = _milestone_order(pathway)
    first_milestone_date = None
    for field_name in milestone_fields:
        d = _parse(patient.get(field_name))
        if d:
            first_milestone_date = d
            break
    intervals["npv_to_next_step_days"] = _days_between(npv, first_milestone_date)

    if intervals["referral_to_definitive_days"] is None and referral:
        last = definitive_date
        if last is None:
            for field_name in reversed(milestone_fields):
                d = _parse(patient.get(field_name))
                if d:
                    last = d
                    break
        last = last or npv or referral
        base_remaining = {"Surgery-First": 40, "Neoadjuvant Therapy": 70, "Radiation-First": 55,
                           "Systemic Therapy Only": 30}.get(pathway, 45)
        remaining = base_remaining + (20 if patient.get("scheduling_status") == "Delayed" else 0)
        intervals["projected_total_days"] = (last - referral).days + remaining
    else:
        intervals["projected_total_days"] = intervals["referral_to_definitive_days"]

    primary = "None identified"
    secondary = ""
    if not patient["imaging_complete"]:
        primary = "Imaging incomplete"
        secondary = "Staging / planning incomplete"
    elif not patient["pathology_received"]:
        primary = "Pathology not received"
        secondary = "Blocks tumor board review and treatment planning"
    elif patient["biomarker_testing_status"] in ("Pending", "Not Ordered"):
        primary = "Biomarker/genomic testing not resolved"
        secondary = "Blocks treatment selection (targeted therapy eligibility)"
    elif patient["insurance_auth_status"] == "Pending":
        primary = "Insurance authorization pending"
        secondary = "Prevents firm treatment start booking"
    elif patient["insurance_auth_status"] == "Denied":
        primary = "Insurance authorization denied"
        secondary = "Requires appeal / peer-to-peer review"
    elif not patient["tumor_board_date"]:
        primary = "Tumor board review not scheduled"
        secondary = "Multidisciplinary conference capacity or intake lag"
    elif pathway in ("Surgery-First", "Neoadjuvant Therapy") and not patient["surgical_discussion_date"]:
        primary = "Surgical discussion not scheduled"
        secondary = "Provider template / coordinator bandwidth"
    elif pathway == "Radiation-First" and not patient["radiation_start_date"] and patient["radiation_planning_date"]:
        primary = "Radiation start delayed after planning"
        secondary = "Linac / treatment slot capacity"
    elif patient["no_show_count"] >= 3:
        primary = "Repeated no-shows disrupting scheduling"
        secondary = "Consider transportation support / reminder outreach"
    elif intervals.get("projected_total_days") and intervals["projected_total_days"] > 150:
        primary = "Long overall projected diagnosis-to-treatment interval"
        secondary = "Review end-to-end pathway capacity for this diagnosis/pathway"
    elif patient["scheduling_status"] == "Delayed":
        primary = "General capacity or coordination lag"
        secondary = "Review open slots and cancellation list"

    intervals["primary_bottleneck"] = primary
    intervals["secondary_note"] = secondary
    return intervals
