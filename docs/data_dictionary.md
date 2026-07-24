# Data Dictionary

Authoritative column-level definitions live in `oncology_pipeline/db/schema.sql`; this document
describes each table's purpose and any non-obvious columns. All ids use the `ONC-*` namespace
(`oncology_pipeline/identifiers.py`).

| Table | Purpose | Notable columns |
|---|---|---|
| `facilities` | ~85 synthetic sites (comprehensive centers, surgical hospitals, infusion/radiation/imaging centers, reference labs) | `tax_id`/`lab_id` are deliberately non-standard formats, never real-looking |
| `providers` | 45 synthetic clinicians | `facility_id` = home site |
| `coordinators` | 12 synthetic care coordinators | referenced by `patients.assigned_coordinator_id` |
| `payers` / `payer_plans` | 32 synthetic payer orgs, 1-3 plans each | `payer_type` in Commercial/Medicare/Medicaid |
| `facility_capabilities` | per-facility service capacity/lead time | `service_type` matches a `PATHWAY_STEPS` step; drives slot matching |
| `payer_facility_network` | service-specific in-network flags | one row per (payer, plan, facility, service_type) -- a facility can be in-network for imaging but not surgery |
| `disease_reference` | versioned diagnosis-to-ICD-10-CM mapping | see `docs/source_provenance.md`; `mapping_status` is `mapped`/`not_mapped` |
| `patients` | one row per synthetic patient | `payer_type` always set; `payer_id`/`plan_id` null for Uninsured; `dx_mapping_status` mirrors `disease_reference` |
| `referrals` | referral + new-patient-visit dates | one per patient |
| `pathway_milestones` | normalized (long-format) milestone chain | `fact_id` = `f"{patient_id}:{field_name}"`, the stable id cited by LLM `supporting_fact_ids` |
| `appointments` / `encounters` | derived visit records | `milestone_fact_id` links an appointment back to its originating milestone fact |
| `diagnostic_orders` / `diagnostic_results` | imaging/pathology/biomarker workup | `status` reflects `patients.imaging_complete`/`pathology_received`/`biomarker_testing_status` |
| `authorizations` | one per patient's auth-gated pathway step | `cpt_code` mapped by service type (pre-op/infusion/radiation) |
| `portal_events` | patient-portal activity log | referral-received + appointment-reminder events |
| `documents` | pathology/imaging reports, auth letters | linked via `related_order_id`/`related_auth_id` |
| `agent_outputs` | one row per (run, patient) deterministic-agent result | `narrative_source` = `deterministic_template` or `openrouter_llm` |
| `llm_case_narratives` | one row per successful LLM patient-case call | mirrors `llm.schemas.PatientCaseNarrative` exactly |
| `slot_recommendations` | ranked candidate slots for each patient's next pending step | `reason_code` explains the ranking (see `docs/methodology.md`) |
| `run_metadata` / `scenario_runs` | per-run provenance | `scenario_name`, `random_seed`, `dataset_type='synthetic'` |

## LLM usage ledger (`outputs/llm_usage_ledger.csv`, not a DB table)

One row per attempted LLM request (including cache hits and fallbacks): `run_id`, `timestamp`,
`request_type` (`patient_case`/`cohort_synthesis`), `patient_or_cohort_id`, `requested_model`,
`actual_model` (what the API actually reported -- see the model-substitution incident in
`docs/architecture.md`), `prompt_version`, `input_tokens`, `output_tokens`, `reasoning_tokens`,
`cache_hit`, `retry_count`, `reported_cost`, `cumulative_run_cost`, `success_or_fallback_status`,
`fallback_reason`, `schema_validation_status`. Never contains the API key or full raw prompts/
responses.
