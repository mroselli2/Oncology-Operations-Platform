# Methodology

## Synthetic cohort generation

A fixed random seed (42) plus per-entity-type seeded RNG streams (`generation/cohort.py`) produce
a deterministic, reproducible 1200-patient cohort across four branching care pathways
(Surgery-First, Neoadjuvant Therapy, Radiation-First, Systemic Therapy Only), each defined as an
ordered milestone chain in `generation/core.py::PATHWAY_STEPS`. A patient's pathway is chosen by
cancer-type-specific weights, skewed toward palliative/systemic care at Stage IV. Six hand-crafted
`FORCED_SCENARIOS` guarantee specific illustrative cases (pathology lag, capacity wait, imaging
incomplete, auth pending, a completed journey, biomarker turnaround) regardless of the random draw,
so every run's reports include concrete, representative examples of each bottleneck type.

Delay/backlog behavior is controlled by named **scenario presets** (`scenarios/scenario_configs.yaml`
-- `baseline`, `high_backlog`, `holiday_surge`), not hardcoded constants, so the effect of capacity
strain on the whole cohort is inspectable and reproducible.

## Deterministic agents

Five agents (`agents/intake.py` .. `communication.py`) run per patient, reading from
`db.queries.get_patient_full()` (a joined, wide-row reconstruction of the normalized
`pathway_milestones` table):

1. **Intake Review** -- flags missing prerequisites (imaging, pathology, biomarker, auth, tumor
   board, pathway-specific next visit).
2. **Bottleneck Detection** -- computes referral/NPV/milestone intervals and names the single
   dominant delay driver, checked in a fixed clinical/operational priority order.
3. **Risk Scoring** -- a 0-100 score from timeline length, missing items, clinical acuity (stage,
   ECOG, comorbidities), and access factors (payer type, no-shows), mapped to High/Moderate/Low.
4. **Recommendation** -- a concrete next action keyed off the primary bottleneck.
5. **Communication Drafting** -- an internal-only coordinator note; this is also the deterministic
   template used whenever the LLM layer is off, budget-exhausted, or fails validation.

## Slot matching

`agents/slot_matching.py` finds each patient's earliest not-yet-scheduled pathway step
(`db.queries.get_next_pending_step`) and ranks real candidate facilities
(`db.queries.get_slot_candidates`) by: network tier (in-network > unknown/no-plan > out-of-network),
then lead time, then a stable synthetic distance. Each ranked candidate gets an explicit
`reason_code` (`PREREQUISITE_PENDING`, `CANCELLATION_LIST`, `IN_NETWORK_PREFERRED`,
`NEXT_AVAILABLE`, `CLOSEST_FACILITY`) so every recommendation is traceable to the fact that produced
it. This is pure deterministic Python -- the LLM layer may narrate a slot recommendation but never
computes or alters one.

## LLM narrative layer (optional, bounded)

When enabled (`--llm-mode auto|on`), up to 15 highest-risk active patients plus one cohort-level
synthesis are sent compact fact packets (`llm/fact_packet.py`) built entirely from already-computed
deterministic values -- never a raw table or the full cohort. The model (fixed to
`openai/gpt-oss-20b` unless overridden) returns JSON validated against a Pydantic schema
(`llm/schemas.py`); every cited `supporting_fact_ids` entry must resolve to a real fact the
deterministic engine produced, or the response is rejected. A hard per-run USD budget
(`llm/budget.py`, default $0.10) and call cap (17) are enforced before every call, and any failure
mode (timeout, rate limit, malformed JSON, schema failure, unsupported fact id, model substitution,
budget exhaustion, missing key) falls back to the deterministic template from step 5 above -- the
pipeline never fails solely because the LLM layer is unavailable.

See `docs/architecture.md` for the model-substitution incident this layer's response verification
was built to catch, and the current (not yet live-confirmed) status of that fix.
