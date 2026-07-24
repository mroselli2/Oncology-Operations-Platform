-- Oncology Pipeline SQLite schema. All ids use the ONC-* namespace (see
-- oncology_pipeline/identifiers.py). Rebuilt from scratch on every pipeline
-- run (see db/loader.py) -- run_metadata/scenario_runs provide per-run
-- provenance rather than the DB accumulating history across runs.

PRAGMA foreign_keys = ON;

CREATE TABLE facilities (
    facility_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    facility_type   TEXT,
    city            TEXT,
    state           TEXT,
    tax_id          TEXT,
    lab_id          TEXT
);

CREATE TABLE providers (
    provider_id     TEXT PRIMARY KEY,
    full_name       TEXT NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    specialty       TEXT,
    facility_id     TEXT REFERENCES facilities(facility_id)
);

CREATE TABLE coordinators (
    coordinator_id  TEXT PRIMARY KEY,
    full_name       TEXT NOT NULL
);

CREATE TABLE payers (
    payer_id        TEXT PRIMARY KEY,
    payer_name      TEXT NOT NULL,
    payer_type      TEXT,
    phone           TEXT
);

CREATE TABLE payer_plans (
    plan_id         TEXT PRIMARY KEY,
    payer_id        TEXT REFERENCES payers(payer_id),
    plan_type       TEXT
);

CREATE TABLE facility_capabilities (
    facility_id         TEXT REFERENCES facilities(facility_id),
    service_type        TEXT,
    available           INTEGER,
    weekly_capacity      INTEGER,
    avg_lead_time_days     INTEGER,
    notes                    TEXT,
    PRIMARY KEY (facility_id, service_type)
);

CREATE TABLE payer_facility_network (
    network_id      TEXT PRIMARY KEY,
    payer_id        TEXT REFERENCES payers(payer_id),
    plan_id         TEXT REFERENCES payer_plans(plan_id),
    facility_id     TEXT REFERENCES facilities(facility_id),
    service_type    TEXT,
    in_network      INTEGER,
    contracted_since TEXT
);

CREATE TABLE disease_reference (
    disease_ref_id          TEXT PRIMARY KEY,
    cancer_type             TEXT,
    stage_system             TEXT,
    icd10_code                 TEXT,
    mapping_status               TEXT,
    notes                          TEXT,
    reference_dataset_version        TEXT
);

CREATE TABLE patients (
    patient_id              TEXT PRIMARY KEY,
    mrn                     TEXT UNIQUE NOT NULL,
    first_name TEXT, last_name TEXT, dob TEXT, age INTEGER, gender TEXT,
    diagnosis_type           TEXT,
    primary_dx_code           TEXT,
    dx_mapping_status          TEXT,
    stage                        TEXT,
    ecog_status                    INTEGER,
    comorbidity_count                INTEGER,
    treatment_modality_pathway         TEXT,
    priority_level                       TEXT,
    payer_type                             TEXT,
    payer_id                                 TEXT REFERENCES payers(payer_id),
    plan_id                                    TEXT REFERENCES payer_plans(plan_id),
    facility_id                                  TEXT REFERENCES facilities(facility_id),
    assigned_provider_id                           TEXT REFERENCES providers(provider_id),
    assigned_coordinator_id                          TEXT REFERENCES coordinators(coordinator_id),
    referral_source TEXT,
    distance_miles REAL,
    no_show_count INTEGER,
    reschedule_count INTEGER,
    insurance_auth_status TEXT,
    imaging_complete INTEGER,
    pathology_received INTEGER,
    biomarker_testing_status TEXT,
    scheduling_status TEXT,
    barrier_reason TEXT,
    definitive_treatment_type TEXT,
    definitive_treatment_date TEXT,
    dataset_type TEXT DEFAULT 'synthetic',
    synthetic_data_version TEXT
);

CREATE TABLE referrals (
    referral_id             TEXT PRIMARY KEY,
    patient_id              TEXT REFERENCES patients(patient_id),
    referral_date            TEXT,
    referral_source            TEXT,
    referring_provider_id        TEXT REFERENCES providers(provider_id),
    new_patient_visit_date         TEXT
);

CREATE TABLE pathway_milestones (
    fact_id           TEXT PRIMARY KEY,
    patient_id         TEXT REFERENCES patients(patient_id),
    pathway              TEXT,
    field_name              TEXT,
    sequence_index             INTEGER,
    gate_type                    TEXT,
    service_type                   TEXT,
    milestone_date                   TEXT,
    barrier_reason                     TEXT
);

CREATE TABLE appointments (
    appointment_id     TEXT PRIMARY KEY,
    patient_id          TEXT REFERENCES patients(patient_id),
    provider_id           TEXT REFERENCES providers(provider_id),
    facility_id             TEXT REFERENCES facilities(facility_id),
    appointment_type_code     TEXT,
    scheduled_date               TEXT,
    status                          TEXT,
    milestone_fact_id                 TEXT REFERENCES pathway_milestones(fact_id)
);

CREATE TABLE encounters (
    encounter_id       TEXT PRIMARY KEY,
    appointment_id       TEXT REFERENCES appointments(appointment_id),
    patient_id              TEXT REFERENCES patients(patient_id),
    provider_id                TEXT REFERENCES providers(provider_id),
    facility_id                   TEXT REFERENCES facilities(facility_id),
    encounter_date                   TEXT,
    encounter_type                      TEXT,
    notes_summary                          TEXT
);

CREATE TABLE diagnostic_orders (
    order_id            TEXT PRIMARY KEY,
    patient_id            TEXT REFERENCES patients(patient_id),
    order_type              TEXT,
    order_detail                TEXT,
    ordering_provider_id           TEXT REFERENCES providers(provider_id),
    order_date                        TEXT,
    status                                TEXT
);

CREATE TABLE diagnostic_results (
    result_id            TEXT PRIMARY KEY,
    order_id                TEXT REFERENCES diagnostic_orders(order_id),
    patient_id                  TEXT REFERENCES patients(patient_id),
    result_date                    TEXT,
    result_status                     TEXT,
    result_detail                        TEXT
);

CREATE TABLE authorizations (
    auth_id                TEXT PRIMARY KEY,
    patient_id                TEXT REFERENCES patients(patient_id),
    payer_id                     TEXT REFERENCES payers(payer_id),
    plan_id                        TEXT REFERENCES payer_plans(plan_id),
    ordering_provider_id              TEXT REFERENCES providers(provider_id),
    facility_id                          TEXT REFERENCES facilities(facility_id),
    cpt_code TEXT, cpt_description TEXT, primary_dx_code TEXT,
    auth_status TEXT,
    authorization_code TEXT,
    validity_start TEXT, validity_end TEXT,
    peer_to_peer_required INTEGER,
    third_party_reviewer TEXT,
    reviewer_name TEXT,
    num_clinical_questions_asked INTEGER,
    total_time_spent_on_phone_min INTEGER,
    denial_reason TEXT,
    request_date TEXT, decision_date TEXT
);

CREATE TABLE portal_events (
    event_id              TEXT PRIMARY KEY,
    patient_id               TEXT REFERENCES patients(patient_id),
    event_type                  TEXT,
    event_timestamp                TEXT,
    related_appointment_id            TEXT REFERENCES appointments(appointment_id)
);

CREATE TABLE documents (
    document_id           TEXT PRIMARY KEY,
    patient_id                TEXT REFERENCES patients(patient_id),
    document_type                 TEXT,
    related_order_id                 TEXT REFERENCES diagnostic_orders(order_id),
    related_auth_id                     TEXT REFERENCES authorizations(auth_id),
    created_date TEXT, status TEXT
);

CREATE TABLE agent_outputs (
    run_id                TEXT,
    patient_id               TEXT REFERENCES patients(patient_id),
    generated_at                TEXT,
    missing_items                  TEXT,
    primary_bottleneck                TEXT,
    secondary_note                       TEXT,
    risk_score                              INTEGER,
    risk_level                                TEXT,
    projected_total_days                        INTEGER,
    recommended_action                             TEXT,
    internal_draft_note                               TEXT,
    narrative_source                                    TEXT,
    PRIMARY KEY (run_id, patient_id)
);

CREATE TABLE llm_case_narratives (
    run_id TEXT, patient_id TEXT, operational_summary TEXT, primary_bottleneck TEXT,
    priority_rationale TEXT, recommended_next_action TEXT, internal_coordinator_note TEXT,
    supporting_fact_ids TEXT, uncertainty_statement TEXT, human_review_required INTEGER,
    generated_by TEXT, model_name TEXT,
    PRIMARY KEY (run_id, patient_id)
);

CREATE TABLE slot_recommendations (
    slot_recommendation_id  TEXT PRIMARY KEY,
    run_id                     TEXT,
    patient_id                    TEXT REFERENCES patients(patient_id),
    appointment_type_code            TEXT,
    rank                                 INTEGER,
    candidate_facility_id                   TEXT REFERENCES facilities(facility_id),
    candidate_provider_id                      TEXT REFERENCES providers(provider_id),
    candidate_date                                TEXT,
    prerequisites_met                                INTEGER,
    authorization_status                                TEXT,
    network_status                                        TEXT,
    distance_miles                                          REAL,
    cancellation_opening                                       INTEGER,
    reason_code                                                   TEXT
);

CREATE TABLE run_metadata (
    run_id                TEXT PRIMARY KEY,
    generated_at              TEXT,
    random_seed                 INTEGER,
    cohort_size                    INTEGER,
    dataset_type                     TEXT DEFAULT 'synthetic',
    synthetic_data_version              TEXT,
    scenario_name                          TEXT,
    llm_mode                                  TEXT,
    llm_model                                    TEXT
);

CREATE TABLE scenario_runs (
    run_id           TEXT PRIMARY KEY,
    scenario_name       TEXT,
    parameters_json         TEXT
);

CREATE INDEX idx_pathway_milestones_patient ON pathway_milestones(patient_id);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_encounters_patient ON encounters(patient_id);
CREATE INDEX idx_diagnostic_orders_patient ON diagnostic_orders(patient_id);
CREATE INDEX idx_authorizations_patient ON authorizations(patient_id);
CREATE INDEX idx_documents_patient ON documents(patient_id);
CREATE INDEX idx_network_payer_facility ON payer_facility_network(payer_id, facility_id, service_type);
