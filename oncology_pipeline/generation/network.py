"""Payer-facility network contracts and facility service capabilities.

A facility can be in-network for imaging but not surgery; capacity and lead
time here feed the slot-matching engine directly.
"""

from __future__ import annotations

import random

from .. import identifiers as ids

CAPACITY_BASELINE = {
    "surgery": (8, 20),
    "tumor_board": (10, 25),
    "imaging": (30, 80),
    "lab": (50, 150),
    "pathology": (50, 150),
    "infusion": (40, 100),
    "radiation": (20, 50),
    "surgical_discussion": (15, 35),
    "pre_op": (15, 35),
}

LEAD_TIME_BASELINE = {
    "surgery": (10, 25),
    "tumor_board": (5, 14),
    "imaging": (3, 10),
    "lab": (2, 7),
    "pathology": (2, 7),
    "infusion": (5, 15),
    "radiation": (7, 15),
    "surgical_discussion": (5, 14),
    "pre_op": (5, 14),
}

IN_NETWORK_PROB_BY_PAYER_TYPE = {"Commercial": 0.75, "Medicare": 0.70, "Medicaid": 0.55}


def build_facility_capabilities(
    rng: random.Random, facilities: list[dict], capacity_multiplier: float = 1.0,
    offset_multiplier: float = 1.0,
) -> list[dict]:
    rows = []
    for facility in facilities:
        for service in facility["services"]:
            lo, hi = CAPACITY_BASELINE[service]
            weekly_capacity = max(1, round(rng.randint(lo, hi) * capacity_multiplier))
            lead_lo, lead_hi = LEAD_TIME_BASELINE[service]
            avg_lead_time_days = max(1, round(rng.randint(lead_lo, lead_hi) * offset_multiplier))
            rows.append({
                "facility_id": facility["facility_id"],
                "service_type": service,
                "available": True,
                "weekly_capacity": weekly_capacity,
                "avg_lead_time_days": avg_lead_time_days,
                "notes": "",
            })
    return rows


def build_payer_facility_network(
    rng: random.Random, payers: list[dict], plans: list[dict], facilities: list[dict],
) -> list[dict]:
    plans_by_payer: dict[str, list[dict]] = {}
    for plan in plans:
        plans_by_payer.setdefault(plan["payer_id"], []).append(plan)

    rows = []
    seq = 0
    for payer in payers:
        prob = IN_NETWORK_PROB_BY_PAYER_TYPE[payer["payer_type"]]
        payer_plans = plans_by_payer.get(payer["payer_id"], [])
        for facility in facilities:
            for service in facility["services"]:
                in_network = rng.random() < prob
                for plan in payer_plans:
                    seq += 1
                    rows.append({
                        "network_id": ids.network_id(seq),
                        "payer_id": payer["payer_id"],
                        "plan_id": plan["plan_id"],
                        "facility_id": facility["facility_id"],
                        "service_type": service,
                        "in_network": in_network,
                        "contracted_since": "2023-01-01" if in_network else None,
                    })
    return rows
