"""Orchestrates one full deterministic cohort build.

Each generator draws from its own seeded RNG stream (per-entity-type salt)
rather than one shared stream, so reordering generators later can't
perturb output for unrelated entity types.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import appointments as appt_gen
from . import core
from . import disease_reference
from . import insurance as insurance_gen
from . import network as network_gen
from . import patients as patients_gen

RANDOM_SEED = 42
DEFAULT_COHORT_SIZE = 1200
TODAY = datetime(2026, 7, 23)

SCENARIOS_FILE = Path(__file__).parent.parent / "scenarios" / "scenario_configs.yaml"

_SALTS = {
    "facilities": 1, "providers": 2, "coordinators": 3, "payers": 4, "plans": 5,
    "network": 6, "capabilities": 7, "patients": 8, "insurance": 9,
    "appointments": 10, "diagnostics": 11, "portal": 12, "documents": 13,
}


def _rng(name: str, seed: int = RANDOM_SEED) -> random.Random:
    return random.Random(seed + _SALTS[name])


def load_scenarios() -> dict:
    with open(SCENARIOS_FILE) as f:
        return yaml.safe_load(f)


def build_cohort(
    scenario_name: str = "baseline", cohort_size: int = DEFAULT_COHORT_SIZE,
    today: datetime = TODAY, random_seed: int = RANDOM_SEED, run_id: str = "run-001",
) -> dict[str, list[dict]]:
    scenarios = load_scenarios()
    if scenario_name not in scenarios:
        raise ValueError(f"Unknown scenario '{scenario_name}'. Available: {list(scenarios)}")
    scenario = scenarios[scenario_name]

    facilities = core.build_facilities(_rng("facilities", random_seed))
    providers = core.build_providers(_rng("providers", random_seed), facilities)
    coordinators = core.build_coordinators(_rng("coordinators", random_seed))
    payers = core.build_payers(_rng("payers", random_seed))
    plans = core.build_payer_plans(_rng("plans", random_seed), payers)

    facility_capabilities = network_gen.build_facility_capabilities(
        _rng("capabilities", random_seed), facilities,
        capacity_multiplier=scenario["capacity_multiplier"],
        offset_multiplier=scenario["offset_multiplier"],
    )
    payer_facility_network = network_gen.build_payer_facility_network(
        _rng("network", random_seed), payers, plans, facilities,
    )

    disease_lookup = disease_reference.disease_reference_lookup()

    patients, referrals, pathway_milestones = patients_gen.generate_patients(
        _rng("patients", random_seed), scenario, today, cohort_size,
        payers, plans, providers, coordinators, disease_lookup,
    )

    authorizations = insurance_gen.build_authorizations(
        _rng("insurance", random_seed), patients, pathway_milestones,
    )

    appointments, encounters = appt_gen.build_appointments_and_encounters(
        _rng("appointments", random_seed), patients, referrals, pathway_milestones, today,
    )
    diagnostic_orders, diagnostic_results = appt_gen.build_diagnostic_orders_results(
        _rng("diagnostics", random_seed), patients, referrals,
    )
    portal_events = appt_gen.build_portal_events(_rng("portal", random_seed), patients, appointments)
    documents = appt_gen.build_documents(_rng("documents", random_seed), patients, diagnostic_orders, authorizations)

    run_metadata = [{
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": random_seed,
        "cohort_size": cohort_size,
        "dataset_type": "synthetic",
        "synthetic_data_version": "v1.0.0",
        "scenario_name": scenario_name,
        "llm_mode": None,
        "llm_model": None,
    }]
    scenario_runs = [{
        "run_id": run_id, "scenario_name": scenario_name,
        "parameters_json": str(scenario),
    }]

    disease_reference_rows = disease_reference.load_disease_reference().to_dict("records")

    return {
        "facilities": facilities,
        "providers": providers,
        "coordinators": coordinators,
        "payers": payers,
        "payer_plans": plans,
        "facility_capabilities": facility_capabilities,
        "payer_facility_network": payer_facility_network,
        "disease_reference": disease_reference_rows,
        "patients": patients,
        "referrals": referrals,
        "pathway_milestones": pathway_milestones,
        "authorizations": authorizations,
        "appointments": appointments,
        "encounters": encounters,
        "diagnostic_orders": diagnostic_orders,
        "diagnostic_results": diagnostic_results,
        "portal_events": portal_events,
        "documents": documents,
        "run_metadata": run_metadata,
        "scenario_runs": scenario_runs,
    }


if __name__ == "__main__":
    from ..db.loader import build_database

    data = build_cohort()
    for table, rows in data.items():
        print(f"{table}: {len(rows)} rows")

    db_path = Path(__file__).parent.parent.parent / "data" / "oncology_pipeline.db"
    build_database(data, db_path)
    print(f"\nLoaded into {db_path}")
