"""Patient demographics and pathway/milestone-chain generation.

Emits long-format pathway_milestones facts (each with a stable fact_id)
rather than wide per-patient columns.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import identifiers as ids
from . import core

HOLIDAY_WINDOWS = [
    (datetime(2025, 11, 15), datetime(2026, 1, 5)),
]


def business_day(d: datetime) -> datetime:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def in_holiday_window(d: datetime) -> bool:
    return any(start <= d <= end for start, end in HOLIDAY_WINDOWS)


def offset_date(rng: random.Random, base: datetime, lo: int, hi: int, scenario: dict, extra_delay: int = 0) -> datetime:
    lo_s = max(1, round(lo * scenario["offset_multiplier"]))
    hi_s = max(lo_s, round(hi * scenario["offset_multiplier"]))
    d = base + timedelta(days=rng.randint(lo_s, hi_s) + extra_delay)
    if in_holiday_window(d):
        h_lo, h_hi = scenario["holiday_extra_days"]
        d += timedelta(days=rng.randint(h_lo, h_hi))
    return business_day(d)


def random_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(days=rng.randint(0, max(delta.days, 0)))


def weighted_choice(rng: random.Random, options: list, weights: list):
    return rng.choices(options, weights=weights)[0]


def gen_stage_ecog_comorbidity(rng: random.Random, age: int) -> tuple[str, int, int]:
    stage = weighted_choice(rng, core.STAGES, [0.22, 0.28, 0.30, 0.20])
    stage_idx = core.STAGES.index(stage)
    ecog_weights = [max(0.05, 0.5 - 0.12 * stage_idx), 0.30, 0.20 + 0.08 * stage_idx,
                     0.05 + 0.05 * stage_idx, 0.02 + 0.03 * stage_idx]
    ecog = weighted_choice(rng, core.ECOG_STATUSES, ecog_weights)
    comorbidity_lambda = 0.5 + max(0, age - 50) / 25
    comorbidity_count = min(6, sum(1 for _ in range(6) if rng.random() < comorbidity_lambda / 6))
    return stage, ecog, comorbidity_count


def gen_pathway(rng: random.Random, diagnosis: str, stage: str) -> str:
    if stage == "IV" and rng.random() < 0.5:
        return "Systemic Therapy Only"
    return weighted_choice(rng, core.TREATMENT_PATHWAYS, core.PATHWAY_WEIGHTS[diagnosis])


def priority_from_clinical(rng: random.Random, stage: str, ecog: int) -> str:
    if stage in ("III", "IV") or ecog >= 2:
        return weighted_choice(rng, ["High", "Medium"], [0.75, 0.25])
    return weighted_choice(rng, ["High", "Medium", "Low"], [0.15, 0.45, 0.40])


def run_pathway_chain(
    rng: random.Random, patient_id: str, pathway: str, npv: datetime, prereqs_ok: bool,
    prereq_barrier: str, auth_status: str, extra_delay: int, scenario: dict, today: datetime,
) -> tuple[list[dict], str, str, datetime | None, str]:
    """Walk a pathway's milestone chain. Returns (milestone_facts, status,
    barrier, definitive_date, definitive_field)."""
    steps = core.PATHWAY_STEPS[pathway]
    current = npv
    barrier = ""
    chain_broken = False
    facts = []

    for seq_idx, (name, lo, hi, gate, service_type) in enumerate(steps, start=1):
        if chain_broken:
            facts.append({
                "fact_id": ids.fact_id(patient_id, name), "patient_id": patient_id,
                "pathway": pathway, "field_name": name, "sequence_index": seq_idx,
                "gate_type": gate, "service_type": service_type,
                "milestone_date": None, "barrier_reason": None,
            })
            continue
        if gate == "prereqs" and not prereqs_ok:
            barrier = prereq_barrier
            chain_broken = True
            facts.append({
                "fact_id": ids.fact_id(patient_id, name), "patient_id": patient_id,
                "pathway": pathway, "field_name": name, "sequence_index": seq_idx,
                "gate_type": gate, "service_type": service_type,
                "milestone_date": None, "barrier_reason": barrier,
            })
            continue
        if gate == "auth" and auth_status not in ("Approved", "Not Required"):
            barrier = (
                "Insurance authorization denied – appeal needed" if auth_status == "Denied"
                else "Insurance authorization pending"
            )
            chain_broken = True
            facts.append({
                "fact_id": ids.fact_id(patient_id, name), "patient_id": patient_id,
                "pathway": pathway, "field_name": name, "sequence_index": seq_idx,
                "gate_type": gate, "service_type": service_type,
                "milestone_date": None, "barrier_reason": barrier,
            })
            continue

        nd = offset_date(rng, current, lo, hi, scenario, extra_delay=extra_delay if seq_idx == 1 else 0)
        current = nd
        row_barrier = None
        if nd > today:
            chain_broken = True
        facts.append({
            "fact_id": ids.fact_id(patient_id, name), "patient_id": patient_id,
            "pathway": pathway, "field_name": name, "sequence_index": seq_idx,
            "gate_type": gate, "service_type": service_type,
            "milestone_date": nd.strftime("%Y-%m-%d"), "barrier_reason": row_barrier,
        })

    definitive_field = core.DEFINITIVE_FIELD_BY_PATHWAY[pathway]
    definitive_fact = next((f for f in facts if f["field_name"] == definitive_field), None)
    definitive_date = None
    if definitive_fact and definitive_fact["milestone_date"]:
        definitive_date = datetime.strptime(definitive_fact["milestone_date"], "%Y-%m-%d")

    if definitive_date and definitive_date <= today:
        status = "Completed"
        barrier = ""
    elif definitive_date and definitive_date > today:
        status = "Scheduled"
    elif barrier:
        status = "Delayed"
    else:
        status = "In Progress"

    return facts, status, barrier, definitive_date, definitive_field


FORCED_SCENARIOS = {
    0: {"diagnosis": "Colorectal Cancer", "pathway": "Surgery-First", "stage": "III", "ecog": 1,
        "imaging": True, "pathology": False, "biomarker": "Pending", "auth": "Pending",
        "referral": datetime(2025, 9, 12)},
    1: {"diagnosis": "Breast Cancer", "pathway": "Neoadjuvant Therapy", "stage": "II", "ecog": 0,
        "imaging": True, "pathology": True, "biomarker": "Complete", "auth": "Approved",
        "referral": datetime(2025, 8, 5), "extra_delay": 25},
    3: {"diagnosis": "Non-Small Cell Lung Cancer", "pathway": "Neoadjuvant Therapy", "stage": "III", "ecog": 1,
        "imaging": False, "pathology": False, "biomarker": "Not Ordered", "auth": "Pending",
        "referral": datetime(2026, 3, 18)},
    6: {"diagnosis": "Pancreatic Cancer", "pathway": "Radiation-First", "stage": "III", "ecog": 1,
        "imaging": True, "pathology": True, "biomarker": "Not Applicable", "auth": "Pending",
        "referral": datetime(2025, 11, 4)},
    8: {"diagnosis": "Prostate Cancer", "pathway": "Surgery-First", "stage": "I", "ecog": 0,
        "imaging": True, "pathology": True, "biomarker": "Not Applicable", "auth": "Approved",
        "referral": datetime(2025, 7, 22)},
    11: {"diagnosis": "Melanoma", "pathway": "Neoadjuvant Therapy", "stage": "III", "ecog": 1,
         "imaging": True, "pathology": True, "biomarker": "Pending", "auth": "Not Required",
         "referral": datetime(2025, 10, 8)},
}

AUTH_WEIGHTS_BY_PAYER_TYPE = {
    "Commercial": [0.65, 0.20, 0.03, 0.12],
    "Medicare": [0.60, 0.22, 0.03, 0.15],
    "Medicaid": [0.40, 0.40, 0.08, 0.12],
    "Uninsured": [0.25, 0.45, 0.15, 0.15],
}


def generate_patients(
    rng: random.Random, scenario: dict, today: datetime, n: int,
    payers: list[dict], plans: list[dict], providers: list[dict], coordinators: list[dict],
    disease_lookup: dict[str, dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (patients, referrals, pathway_milestone_facts)."""
    plans_by_payer: dict[str, list[dict]] = {}
    for plan in plans:
        plans_by_payer.setdefault(plan["payer_id"], []).append(plan)
    payers_by_type: dict[str, list[dict]] = {}
    for payer in payers:
        payers_by_type.setdefault(payer["payer_type"], []).append(payer)

    patients, referrals, all_facts = [], [], []

    for i in range(1, n + 1):
        p_id = ids.patient_id(i)
        first = rng.choice(core.FIRST_NAMES)
        last = rng.choice(core.LAST_NAMES)
        dob = datetime(rng.randint(1948, 1988), rng.randint(1, 12), rng.randint(1, 28))
        age = today.year - dob.year
        gender = rng.choice(["F", "M"])
        provider = rng.choice(providers)
        coordinator = rng.choice(coordinators)
        payer_type = weighted_choice(rng, ["Commercial", "Medicare", "Medicaid", "Uninsured"], [0.45, 0.25, 0.20, 0.10])
        payer = rng.choice(payers_by_type[payer_type]) if payer_type != "Uninsured" else None
        plan = rng.choice(plans_by_payer[payer["payer_id"]]) if payer else None
        distance = round(rng.uniform(2, 25) if rng.random() > 0.15 else rng.uniform(25, 90), 1)
        no_show_rate = scenario["no_show_high_risk_rate"] if payer_type in ("Medicaid", "Uninsured") else scenario["no_show_base_rate"]
        no_show = sum(1 for _ in range(4) if rng.random() < no_show_rate)
        reschedule = sum(1 for _ in range(4) if rng.random() < 0.12)

        forced = FORCED_SCENARIOS.get(i - 1)
        if forced:
            diagnosis = forced["diagnosis"]
            pathway = forced["pathway"]
            stage = forced["stage"]
            ecog = forced["ecog"]
            _, _, comorbidity_count = gen_stage_ecog_comorbidity(rng, age)
            priority = "High"
            referral = forced["referral"]
            imaging_complete = forced["imaging"]
            pathology_received = forced["pathology"]
            biomarker_status = forced["biomarker"]
            auth_status = forced["auth"]
            extra_delay = forced.get("extra_delay", 0)
        else:
            diagnosis = rng.choice(core.CANCER_TYPES)
            stage, ecog, comorbidity_count = gen_stage_ecog_comorbidity(rng, age)
            pathway = gen_pathway(rng, diagnosis, stage)
            priority = priority_from_clinical(rng, stage, ecog)
            referral = random_date(rng, datetime(2025, 7, 15), datetime(2026, 6, 20))
            imaging_complete = rng.random() < scenario["imaging_complete_prob"]
            pathology_received = rng.random() < scenario["pathology_received_prob"]
            if diagnosis in core.BIOMARKER_APPLICABLE:
                biomarker_status = weighted_choice(rng, ["Complete", "Pending", "Not Ordered"], [0.55, 0.30, 0.15])
            else:
                biomarker_status = "Not Applicable"
            auth_weights = AUTH_WEIGHTS_BY_PAYER_TYPE[payer_type]
            auth_status = weighted_choice(rng, ["Approved", "Pending", "Denied", "Not Required"], auth_weights)
            d_lo, d_hi = scenario["extra_delay_per_no_show"]
            r_lo, r_hi = scenario["extra_delay_per_reschedule"]
            extra_delay = no_show * rng.randint(d_lo, d_hi) + reschedule * rng.randint(r_lo, r_hi)

        npv = business_day(referral + timedelta(days=rng.randint(9, 28)))
        prereqs_ok = imaging_complete and pathology_received and biomarker_status in ("Complete", "Not Applicable")
        if not imaging_complete:
            prereq_barrier = "Imaging not completed"
        elif not pathology_received:
            prereq_barrier = "Pathology not received"
        else:
            prereq_barrier = "Biomarker/genomic testing pending"

        facts, status, barrier, definitive_date, definitive_field = run_pathway_chain(
            rng, p_id, pathway, npv, prereqs_ok, prereq_barrier, auth_status, extra_delay, scenario, today,
        )
        all_facts.extend(facts)

        dx_ref = disease_lookup.get(diagnosis, {})

        patients.append({
            "patient_id": p_id,
            "mrn": ids.mrn(i),
            "first_name": first, "last_name": last,
            "dob": dob.strftime("%Y-%m-%d"), "age": age, "gender": gender,
            "diagnosis_type": diagnosis,
            "primary_dx_code": dx_ref.get("icd10_code") or None,
            "dx_mapping_status": dx_ref.get("mapping_status", "not_mapped"),
            "stage": stage,
            "ecog_status": ecog,
            "comorbidity_count": comorbidity_count,
            "treatment_modality_pathway": pathway,
            "priority_level": priority,
            "payer_type": payer_type,
            "payer_id": payer["payer_id"] if payer else None,
            "plan_id": plan["plan_id"] if plan else None,
            "facility_id": provider["facility_id"],
            "assigned_provider_id": provider["provider_id"],
            "assigned_coordinator_id": coordinator["coordinator_id"],
            "referral_source": rng.choice(["Primary Care", "Emergency Department", "Self-Referral", "Other Specialist"]),
            "distance_miles": distance,
            "no_show_count": no_show,
            "reschedule_count": reschedule,
            "insurance_auth_status": auth_status,
            "imaging_complete": imaging_complete,
            "pathology_received": pathology_received,
            "biomarker_testing_status": biomarker_status,
            "scheduling_status": status,
            "barrier_reason": barrier,
            "definitive_treatment_type": definitive_field,
            "definitive_treatment_date": definitive_date.strftime("%Y-%m-%d") if definitive_date else None,
            "dataset_type": "synthetic",
            "synthetic_data_version": "v1.0.0",
        })

        referrals.append({
            "referral_id": ids.referral_id(i),
            "patient_id": p_id,
            "referral_date": referral.strftime("%Y-%m-%d"),
            "referral_source": patients[-1]["referral_source"],
            "referring_provider_id": None,
            "new_patient_visit_date": npv.strftime("%Y-%m-%d"),
        })

    return patients, referrals, all_facts
