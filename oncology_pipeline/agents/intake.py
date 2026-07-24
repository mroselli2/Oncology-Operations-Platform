"""Intake Review Agent: flags missing prerequisites for progressing the
patient's journey."""

from __future__ import annotations


def review(patient: dict) -> list[str]:
    flags = []
    if not patient["imaging_complete"]:
        flags.append("Missing imaging")
    if not patient["pathology_received"]:
        flags.append("Missing pathology report")
    if patient["biomarker_testing_status"] == "Pending":
        flags.append("Biomarker testing pending")
    elif patient["biomarker_testing_status"] == "Not Ordered":
        flags.append("Biomarker testing not ordered")
    if patient["insurance_auth_status"] == "Pending":
        flags.append("Insurance auth pending")
    if patient["insurance_auth_status"] == "Denied":
        flags.append("Auth denied – needs appeal")
    if not patient["tumor_board_date"] and patient["scheduling_status"] != "Completed":
        flags.append("Tumor board review not scheduled")

    pathway = patient["treatment_modality_pathway"]
    if pathway in ("Surgery-First", "Neoadjuvant Therapy"):
        if patient["tumor_board_date"] and not patient["surgical_discussion_date"] and patient["scheduling_status"] != "Completed":
            flags.append("Surgical discussion not scheduled")
        if patient["surgical_discussion_date"] and not patient["pre_op_clearance_date"] and patient["scheduling_status"] != "Completed":
            flags.append("Pre-op clearance not scheduled")
    if pathway == "Radiation-First" and patient["radiation_planning_date"] and not patient["radiation_start_date"] and patient["scheduling_status"] != "Completed":
        flags.append("Radiation start not scheduled")

    if patient["no_show_count"] >= 2:
        flags.append("Elevated no-show history")
    if not flags and patient["scheduling_status"] == "Delayed":
        flags.append("Capacity / slot availability issue")
    return flags
