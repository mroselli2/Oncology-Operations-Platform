"""Shared reference data: facilities, providers, payers, plans, coordinators,
and clinical constants used across the whole cohort.

Each generator takes an explicit random.Random so callers (cohort.py) can
give every entity type its own seeded stream, keeping generation order-
independent and reproducible.
"""

from __future__ import annotations

import random

from .. import identifiers as ids

# Clinical constants
CANCER_TYPES = [
    "Breast Cancer",
    "Colorectal Cancer",
    "Non-Small Cell Lung Cancer",
    "Prostate Cancer",
    "Melanoma",
    "Pancreatic Cancer",
    "Ovarian Cancer",
    "Head and Neck Cancer",
]

BIOMARKER_APPLICABLE = {"Non-Small Cell Lung Cancer", "Breast Cancer", "Colorectal Cancer"}

STAGES = ["I", "II", "III", "IV"]
ECOG_STATUSES = [0, 1, 2, 3, 4]

TREATMENT_PATHWAYS = ["Surgery-First", "Neoadjuvant Therapy", "Radiation-First", "Systemic Therapy Only"]

PATHWAY_WEIGHTS = {
    "Breast Cancer":               [0.45, 0.40, 0.05, 0.10],
    "Colorectal Cancer":           [0.55, 0.30, 0.05, 0.10],
    "Non-Small Cell Lung Cancer":  [0.25, 0.35, 0.20, 0.20],
    "Prostate Cancer":             [0.55, 0.05, 0.35, 0.05],
    "Melanoma":                    [0.70, 0.10, 0.05, 0.15],
    "Pancreatic Cancer":           [0.20, 0.45, 0.10, 0.25],
    "Ovarian Cancer":              [0.35, 0.45, 0.05, 0.15],
    "Head and Neck Cancer":        [0.30, 0.10, 0.45, 0.15],
}

# Milestone chain per pathway: (field_name, min_days, max_days, gate, service_type)
# gate is "prereqs" (imaging+pathology+biomarker), "auth" (insurance auth), or None.
# service_type ties each step to a facility_capabilities row for slot matching.
PATHWAY_STEPS: dict[str, list[tuple[str, int, int, str | None, str]]] = {
    "Surgery-First": [
        ("tumor_board_date", 7, 21, "prereqs", "tumor_board"),
        ("surgical_discussion_date", 5, 20, None, "surgical_discussion"),
        ("pre_op_clearance_date", 8, 22, "auth", "pre_op"),
        ("surgery_date", 14, 45, None, "surgery"),
    ],
    "Neoadjuvant Therapy": [
        ("tumor_board_date", 7, 21, "prereqs", "tumor_board"),
        ("neoadjuvant_start_date", 10, 25, "auth", "infusion"),
        ("neoadjuvant_end_date", 60, 120, None, "infusion"),
        ("restaging_imaging_date", 7, 14, None, "imaging"),
        ("surgical_discussion_date", 5, 15, None, "surgical_discussion"),
        ("pre_op_clearance_date", 8, 20, None, "pre_op"),
        ("surgery_date", 14, 35, None, "surgery"),
    ],
    "Radiation-First": [
        ("tumor_board_date", 7, 21, "prereqs", "tumor_board"),
        ("radiation_planning_date", 7, 21, "auth", "radiation"),
        ("radiation_start_date", 7, 14, None, "radiation"),
        ("radiation_end_date", 28, 42, None, "radiation"),
        ("reassessment_date", 30, 45, None, "surgical_discussion"),
    ],
    "Systemic Therapy Only": [
        ("tumor_board_date", 7, 21, "prereqs", "tumor_board"),
        ("systemic_therapy_start_date", 10, 21, "auth", "infusion"),
    ],
}

DEFINITIVE_FIELD_BY_PATHWAY = {
    "Surgery-First": "surgery_date",
    "Neoadjuvant Therapy": "surgery_date",
    "Radiation-First": "radiation_end_date",
    "Systemic Therapy Only": "systemic_therapy_start_date",
}

ALL_MILESTONE_FIELDS = [
    "tumor_board_date", "neoadjuvant_start_date", "neoadjuvant_end_date",
    "restaging_imaging_date", "radiation_planning_date", "radiation_start_date",
    "radiation_end_date", "reassessment_date", "surgical_discussion_date",
    "pre_op_clearance_date", "surgery_date", "systemic_therapy_start_date",
]

SERVICE_TYPES = ["tumor_board", "imaging", "lab", "pathology", "surgery",
                  "surgical_discussion", "pre_op", "radiation", "infusion"]

HOLIDAY_WINDOWS_DEFAULT = [("2025-11-15", "2026-01-05")]

# Name pools
FIRST_NAMES = [
    "Jordan", "Alex", "Taylor", "Morgan", "Casey", "Riley", "Quinn",
    "Avery", "Cameron", "Reese", "Parker", "Sawyer", "Harper", "Finley",
    "Dakota", "Skylar", "Emerson", "Rowan", "Charlie", "Sage",
]
LAST_NAMES = [
    "Miller", "Brooks", "Chen", "Garcia", "Thompson", "Nguyen", "Patel",
    "Williams", "Khan", "Lopez", "Kim", "Davis", "Rodriguez", "Martinez",
    "Anderson", "Clark", "Bennett", "Foster", "Reyes", "Sullivan",
]

PROVIDER_SPECIALTIES = [
    "Surgical Oncology", "Medical Oncology", "Radiation Oncology",
    "Hematology-Oncology", "Gynecologic Oncology", "Thoracic Surgery",
    "Colorectal Surgery",
]

COORDINATOR_FIRST = [
    "Nina", "Sam", "Devon", "Rachel", "Malik", "Grace", "Priya", "Ethan",
    "Wanda", "Curtis", "Bianca", "Owen",
]
COORDINATOR_LAST = [
    "Alvarez", "Whitfield", "Park", "O'Brien", "Johnson", "Lindqvist",
    "Choudhury", "Bergstrom", "Delacroix", "Manning", "Ferro", "Castellano",
]

FACILITY_QUALIFIERS = [
    "North", "South", "East", "West", "Central", "Metro", "Bay", "River",
    "Lake", "Valley", "Hillside", "Crestview", "Oakwood", "Cedar", "Elm",
    "Maple", "Pine", "Union", "Liberty", "Franklin", "Jefferson", "Lincoln",
    "Ridgeline", "Harborview", "Fairmont", "Westgate", "Eastbrook",
]
FACILITY_TYPE_TEMPLATES = [
    ("Comprehensive Cancer Center", ["surgery", "imaging", "tumor_board", "surgical_discussion", "pre_op", "infusion", "radiation", "lab", "pathology"]),
    ("Regional Surgical Hospital", ["surgery", "pre_op", "surgical_discussion", "imaging"]),
    ("Outpatient Infusion Center", ["infusion"]),
    ("Radiation Oncology Center", ["radiation"]),
    ("Diagnostic Imaging Center", ["imaging"]),
    ("Reference Laboratory", ["lab", "pathology"]),
    ("Community Oncology Clinic", ["tumor_board", "surgical_discussion", "infusion"]),
]

PAYER_QUALIFIERS = [
    "Meridian", "Cornerstone", "Beacon", "Horizon", "Summit", "Anchor",
    "Pinnacle", "Compass", "Harbor", "Bridgeport", "Redwood", "Ironwood",
    "Silverline", "Cascade", "Northgate", "Fieldstone", "Willowbrook",
    "Brightpath", "Clearview", "Union", "Sterling", "Vantage", "Lodestar",
    "Windward", "Amberfield", "Copperline", "Thistledown", "Granite",
    "Prairiewind", "Overlook",
]
PAYER_NOUNS_BY_TYPE = {
    "Commercial": ["Health Partners", "Assurance", "Health Plan", "Insurance Group", "Health Solutions"],
    "Medicare": ["Medicare Advantage Plan", "Senior Health Alliance", "Medicare Health Network"],
    "Medicaid": ["Medicaid Managed Care", "Community Health Plan", "Care Alliance"],
}
PLAN_TYPES_BY_PAYER_TYPE = {
    "Commercial": ["PPO", "HMO", "EPO", "POS"],
    "Medicare": ["Medicare Advantage HMO", "Medicare Advantage PPO"],
    "Medicaid": ["Medicaid Managed Care"],
}


def build_facilities(rng: random.Random, n: int = 85) -> list[dict]:
    """~85 synthetic facilities spanning surgical hospitals, infusion
    centers, radiation centers, imaging centers, and reference labs."""
    facilities = []
    used_names: set[str] = set()
    seq = 0
    while len(facilities) < n:
        qualifier = rng.choice(FACILITY_QUALIFIERS)
        type_name, services = rng.choice(FACILITY_TYPE_TEMPLATES)
        name = f"{qualifier} {type_name}"
        if name in used_names:
            continue
        used_names.add(name)
        seq += 1
        facilities.append({
            "facility_id": ids.facility_id(seq),
            "name": name,
            "facility_type": type_name,
            "city": f"{qualifier} City",
            "state": rng.choice(["PA", "OH", "NJ", "NY", "MD"]),
            "tax_id": ids.facility_tax_id(seq),
            "lab_id": ids.facility_lab_id(seq) if "lab" in services or "pathology" in services else None,
            "services": services,
        })
    return facilities


def build_providers(rng: random.Random, facilities: list[dict], n: int = 45) -> list[dict]:
    clinical_facilities = [f for f in facilities if f["facility_type"] != "Reference Laboratory"]
    providers = []
    for i in range(1, n + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        specialty = rng.choice(PROVIDER_SPECIALTIES)
        facility = rng.choice(clinical_facilities)
        providers.append({
            "provider_id": ids.provider_id(i),
            "full_name": f"Dr. {first} {last}",
            "first_name": first,
            "last_name": last,
            "specialty": specialty,
            "facility_id": facility["facility_id"],
        })
    return providers


def build_coordinators(rng: random.Random, n: int = 12) -> list[dict]:
    coordinators = []
    used = set()
    seq = 0
    while len(coordinators) < n:
        first = rng.choice(COORDINATOR_FIRST)
        last = rng.choice(COORDINATOR_LAST)
        name = f"{first} {last}"
        if name in used:
            continue
        used.add(name)
        seq += 1
        coordinators.append({"coordinator_id": ids.coordinator_id(seq), "full_name": name})
    return coordinators


def build_payers(rng: random.Random, n: int = 32) -> list[dict]:
    """30+ synthetic payer organizations across Commercial/Medicare/Medicaid."""
    payer_types = ["Commercial"] * 16 + ["Medicare"] * 9 + ["Medicaid"] * 7
    rng.shuffle(payer_types)
    payers = []
    used_names: set[str] = set()
    for i, payer_type in enumerate(payer_types[:n], start=1):
        while True:
            name = f"{rng.choice(PAYER_QUALIFIERS)} {rng.choice(PAYER_NOUNS_BY_TYPE[payer_type])}"
            if name not in used_names:
                used_names.add(name)
                break
        payers.append({
            "payer_id": ids.payer_id(i),
            "payer_name": name,
            "payer_type": payer_type,
            "phone": f"555-{rng.randint(200,999)}-{rng.randint(1000,9999)}",
        })
    return payers


def build_payer_plans(rng: random.Random, payers: list[dict]) -> list[dict]:
    plans = []
    seq = 0
    for payer in payers:
        plan_types = PLAN_TYPES_BY_PAYER_TYPE[payer["payer_type"]]
        for plan_type in rng.sample(plan_types, k=rng.randint(1, len(plan_types))):
            seq += 1
            plans.append({
                "plan_id": ids.payer_plan_id(seq),
                "payer_id": payer["payer_id"],
                "plan_type": plan_type,
            })
    return plans
