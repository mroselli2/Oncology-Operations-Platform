"""Derives appointments, encounters, diagnostic orders/results, portal
events, and documents from the pathway milestone facts.

Appointments and encounters are kept separate: an appointment can be
scheduled without yet having occurred, while an encounter only exists once
the visit is complete.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import identifiers as ids

APPOINTMENT_TYPE_BY_FIELD = {
    "tumor_board_date": "TUMOR_BOARD",
    "surgical_discussion_date": "SURG_DISC",
    "pre_op_clearance_date": "PRE_OP",
    "neoadjuvant_start_date": "INFUSION",
    "restaging_imaging_date": "RESTAGING_IMAGING",
    "radiation_planning_date": "RADIATION_PLANNING",
    "radiation_start_date": "RADIATION_TX",
    "reassessment_date": "REASSESSMENT",
    "systemic_therapy_start_date": "INFUSION",
}
ENCOUNTER_ONLY_FIELDS = {
    "surgery_date": "Surgery",
    "neoadjuvant_end_date": "Neoadjuvant Therapy Completion",
    "radiation_end_date": "Radiation Therapy Completion",
}


def _status(date_str: str | None, today: datetime) -> str:
    if not date_str:
        return "Not Scheduled"
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return "Completed" if d <= today else "Scheduled"


def build_appointments_and_encounters(
    rng: random.Random, patients: list[dict], referrals: list[dict],
    milestone_facts: list[dict], today: datetime,
) -> tuple[list[dict], list[dict]]:
    patients_by_id = {p["patient_id"]: p for p in patients}
    appointments, encounters = [], []
    apt_seq, enc_seq = 0, 0

    for referral in referrals:
        patient = patients_by_id[referral["patient_id"]]
        apt_seq += 1
        status = _status(referral["new_patient_visit_date"], today)
        appointment = {
            "appointment_id": ids.appointment_id(apt_seq),
            "patient_id": patient["patient_id"],
            "provider_id": patient["assigned_provider_id"],
            "facility_id": patient["facility_id"],
            "appointment_type_code": "NPV",
            "scheduled_date": referral["new_patient_visit_date"],
            "status": status,
            "milestone_fact_id": None,
        }
        appointments.append(appointment)
        if status == "Completed":
            enc_seq += 1
            encounters.append({
                "encounter_id": ids.encounter_id(enc_seq),
                "appointment_id": appointment["appointment_id"],
                "patient_id": patient["patient_id"],
                "provider_id": patient["assigned_provider_id"],
                "facility_id": patient["facility_id"],
                "encounter_date": referral["new_patient_visit_date"],
                "encounter_type": "New Patient Visit",
                "notes_summary": f"Initial oncology consult for {patient['diagnosis_type']}.",
            })

    for fact in milestone_facts:
        if not fact["milestone_date"]:
            continue
        patient = patients_by_id[fact["patient_id"]]
        field_name = fact["field_name"]

        if field_name in APPOINTMENT_TYPE_BY_FIELD:
            apt_seq += 1
            status = _status(fact["milestone_date"], today)
            appointment = {
                "appointment_id": ids.appointment_id(apt_seq),
                "patient_id": patient["patient_id"],
                "provider_id": patient["assigned_provider_id"],
                "facility_id": patient["facility_id"],
                "appointment_type_code": APPOINTMENT_TYPE_BY_FIELD[field_name],
                "scheduled_date": fact["milestone_date"],
                "status": status,
                "milestone_fact_id": fact["fact_id"],
            }
            appointments.append(appointment)
            if status == "Completed":
                enc_seq += 1
                encounters.append({
                    "encounter_id": ids.encounter_id(enc_seq),
                    "appointment_id": appointment["appointment_id"],
                    "patient_id": patient["patient_id"],
                    "provider_id": patient["assigned_provider_id"],
                    "facility_id": patient["facility_id"],
                    "encounter_date": fact["milestone_date"],
                    "encounter_type": APPOINTMENT_TYPE_BY_FIELD[field_name],
                    "notes_summary": f"{APPOINTMENT_TYPE_BY_FIELD[field_name]} completed for {patient['diagnosis_type']} ({patient['treatment_modality_pathway']}).",
                })
        elif field_name in ENCOUNTER_ONLY_FIELDS and datetime.strptime(fact["milestone_date"], "%Y-%m-%d") <= today:
            enc_seq += 1
            encounters.append({
                "encounter_id": ids.encounter_id(enc_seq),
                "appointment_id": None,
                "patient_id": patient["patient_id"],
                "provider_id": patient["assigned_provider_id"],
                "facility_id": patient["facility_id"],
                "encounter_date": fact["milestone_date"],
                "encounter_type": ENCOUNTER_ONLY_FIELDS[field_name],
                "notes_summary": f"{ENCOUNTER_ONLY_FIELDS[field_name]} for {patient['diagnosis_type']}.",
            })

    return appointments, encounters


def build_diagnostic_orders_results(
    rng: random.Random, patients: list[dict], referrals: list[dict],
) -> tuple[list[dict], list[dict]]:
    referrals_by_patient = {r["patient_id"]: r for r in referrals}
    orders, results = [], []
    order_seq, result_seq = 0, 0

    for patient in patients:
        referral_date = datetime.strptime(referrals_by_patient[patient["patient_id"]]["referral_date"], "%Y-%m-%d")

        for order_type, is_complete_or_status in [
            ("imaging", patient["imaging_complete"]),
            ("pathology", patient["pathology_received"]),
        ]:
            order_seq += 1
            order_date = referral_date + timedelta(days=rng.randint(1, 10))
            status = "Resulted" if is_complete_or_status else "Pending"
            orders.append({
                "order_id": ids.order_id(order_seq),
                "patient_id": patient["patient_id"],
                "order_type": order_type,
                "order_detail": f"{order_type.title()} workup for {patient['diagnosis_type']}",
                "ordering_provider_id": patient["assigned_provider_id"],
                "order_date": order_date.strftime("%Y-%m-%d"),
                "status": status,
            })
            if is_complete_or_status:
                result_seq += 1
                result_date = order_date + timedelta(days=rng.randint(2, 9))
                results.append({
                    "result_id": ids.result_id(result_seq),
                    "order_id": orders[-1]["order_id"],
                    "patient_id": patient["patient_id"],
                    "result_date": result_date.strftime("%Y-%m-%d"),
                    "result_status": "Complete",
                    "result_detail": f"{order_type.title()} result on file.",
                })

        if patient["diagnosis_type"] in ("Non-Small Cell Lung Cancer", "Breast Cancer", "Colorectal Cancer"):
            order_seq += 1
            order_date = referral_date + timedelta(days=rng.randint(3, 14))
            biomarker_status = patient["biomarker_testing_status"]
            orders.append({
                "order_id": ids.order_id(order_seq),
                "patient_id": patient["patient_id"],
                "order_type": "biomarker",
                "order_detail": f"Biomarker/genomic panel for {patient['diagnosis_type']}",
                "ordering_provider_id": patient["assigned_provider_id"],
                "order_date": order_date.strftime("%Y-%m-%d"),
                "status": "Resulted" if biomarker_status == "Complete" else biomarker_status,
            })
            if biomarker_status == "Complete":
                result_seq += 1
                result_date = order_date + timedelta(days=rng.randint(7, 21))
                results.append({
                    "result_id": ids.result_id(result_seq),
                    "order_id": orders[-1]["order_id"],
                    "patient_id": patient["patient_id"],
                    "result_date": result_date.strftime("%Y-%m-%d"),
                    "result_status": "Complete",
                    "result_detail": "Biomarker panel result on file.",
                })

    return orders, results


def build_portal_events(rng: random.Random, patients: list[dict], appointments: list[dict]) -> list[dict]:
    appointments_by_patient: dict[str, list[dict]] = {}
    for apt in appointments:
        appointments_by_patient.setdefault(apt["patient_id"], []).append(apt)

    events = []
    seq = 0
    for patient in patients:
        seq += 1
        events.append({
            "event_id": ids.portal_event_id(seq),
            "patient_id": patient["patient_id"],
            "event_type": "Referral Received Notification",
            "event_timestamp": None,
            "related_appointment_id": None,
        })
        for apt in appointments_by_patient.get(patient["patient_id"], [])[:2]:
            seq += 1
            events.append({
                "event_id": ids.portal_event_id(seq),
                "patient_id": patient["patient_id"],
                "event_type": "Appointment Reminder Sent",
                "event_timestamp": apt["scheduled_date"],
                "related_appointment_id": apt["appointment_id"],
            })
    return events


def build_documents(
    rng: random.Random, patients: list[dict], orders: list[dict], authorizations: list[dict],
) -> list[dict]:
    orders_by_patient: dict[str, list[dict]] = {}
    for o in orders:
        orders_by_patient.setdefault(o["patient_id"], []).append(o)
    auths_by_patient = {a["patient_id"]: a for a in authorizations}

    documents = []
    seq = 0
    for patient in patients:
        for order in orders_by_patient.get(patient["patient_id"], []):
            if order["status"] == "Resulted":
                seq += 1
                documents.append({
                    "document_id": ids.document_id(seq),
                    "patient_id": patient["patient_id"],
                    "document_type": f"{order['order_type']}_report",
                    "related_order_id": order["order_id"],
                    "related_auth_id": None,
                    "created_date": order["order_date"],
                    "status": "Final",
                })
        auth = auths_by_patient.get(patient["patient_id"])
        if auth and auth["auth_status"] in ("Approved", "Denied"):
            seq += 1
            documents.append({
                "document_id": ids.document_id(seq),
                "patient_id": patient["patient_id"],
                "document_type": "authorization_letter",
                "related_order_id": None,
                "related_auth_id": auth["auth_id"],
                "created_date": auth["decision_date"],
                "status": "Final",
            })
    return documents
