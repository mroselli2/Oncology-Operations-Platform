"""ONC-* identifier formatters.

Ids use deliberately non-standard shapes so nothing here can be mistaken
for a real MRN, NPI, TIN, CLIA number, or insurance member id.
"""

from __future__ import annotations


def _fmt(prefix: str, seq: int, width: int) -> str:
    return f"{prefix}-{seq:0{width}d}"


def patient_id(seq: int) -> str:
    return _fmt("ONC-PAT", seq, 6)


def mrn(seq: int) -> str:
    return _fmt("ONC-MRN", seq, 6)


def referral_id(seq: int) -> str:
    return _fmt("ONC-REF", seq, 6)


def appointment_id(seq: int) -> str:
    return _fmt("ONC-APT", seq, 6)


def encounter_id(seq: int) -> str:
    return _fmt("ONC-ENC", seq, 6)


def authorization_id(seq: int) -> str:
    return _fmt("ONC-AUTH", seq, 6)


def authorization_code(seq: int) -> str:
    return _fmt("ONC-AUTHCODE", seq, 6)


def order_id(seq: int) -> str:
    return _fmt("ONC-ORD", seq, 6)


def result_id(seq: int) -> str:
    return _fmt("ONC-RES", seq, 6)


def portal_event_id(seq: int) -> str:
    return _fmt("ONC-PRT", seq, 6)


def document_id(seq: int) -> str:
    return _fmt("ONC-DOC", seq, 6)


def facility_id(seq: int) -> str:
    return _fmt("ONC-FAC", seq, 4)


def facility_tax_id(seq: int) -> str:
    return f"ONC-TAX-F{seq:04d}"


def facility_lab_id(seq: int) -> str:
    return f"ONC-LAB-F{seq:04d}"


def payer_id(seq: int) -> str:
    return _fmt("ONC-PAY", seq, 3)


def payer_plan_id(seq: int) -> str:
    return _fmt("ONC-PLN", seq, 4)


def provider_id(seq: int) -> str:
    return _fmt("ONC-PRV", seq, 4)


def coordinator_id(seq: int) -> str:
    return _fmt("ONC-COO", seq, 3)


def network_id(seq: int) -> str:
    return _fmt("ONC-NET", seq, 4)


def slot_recommendation_id(seq: int) -> str:
    return _fmt("ONC-SLOT", seq, 6)


def disease_reference_id(seq: int) -> str:
    return _fmt("ONC-DXR", seq, 4)


def fact_id(patient_id_value: str, field_name: str) -> str:
    """Stable id for one deterministic fact, cited in LLM supporting_fact_ids."""
    return f"{patient_id_value}:{field_name}"
