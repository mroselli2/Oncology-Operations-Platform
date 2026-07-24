"""Patient Journey Risk Agent: 0-100 delay-risk score + High/Moderate/Low
label, combining timeline length, missing items, clinical acuity, and
access factors."""

from __future__ import annotations

from typing import Any

from . import intake


def score(patient: dict[str, Any], intervals: dict) -> dict[str, Any]:
    projected = intervals.get("projected_total_days") or intervals.get("referral_to_definitive_days") or 0
    flags = intake.review(patient)

    s = 0
    if projected >= 150:
        s += 35
    elif projected >= 120:
        s += 25
    elif projected >= 90:
        s += 15
    elif projected >= 60:
        s += 5

    if "Missing pathology report" in flags:
        s += 20
    if "Biomarker testing pending" in flags or "Biomarker testing not ordered" in flags:
        s += 10
    if "Insurance auth pending" in flags or "Auth denied – needs appeal" in flags:
        s += 15
    if "Missing imaging" in flags:
        s += 15
    if "Tumor board review not scheduled" in flags:
        s += 10
    if "Elevated no-show history" in flags:
        s += 8

    if patient["stage"] in ("III", "IV"):
        s += 8
    if patient["ecog_status"] >= 2:
        s += 8
    s += min(10, patient["comorbidity_count"] * 2)

    if patient["payer_type"] in ("Medicaid", "Uninsured"):
        s += 6

    if patient["priority_level"] == "High":
        s += 8
    elif patient["priority_level"] == "Medium":
        s += 4

    if patient["scheduling_status"] == "Delayed":
        s += 10
    if patient["scheduling_status"] == "Completed":
        s = max(0, s - 30)

    s = min(100, s)
    level = "High" if s >= 70 else "Moderate" if s >= 40 else "Low"

    return {"risk_score": s, "risk_level": level, "projected_days": projected, "missing_items": flags}
