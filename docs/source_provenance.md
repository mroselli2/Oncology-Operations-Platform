# Source Provenance

## Fully synthetic (generated, no external source)

Patients, providers, coordinators, facilities, payers, payer plans, referrals, pathway milestones,
appointments, encounters, diagnostic orders/results, authorizations, portal events, documents, and
all narrative text (deterministic templates and LLM narratives). All produced by
`oncology_pipeline/generation/*` from seeded RNG streams -- see `docs/methodology.md`.

## Derived from a real public reference (not PHI)

`oncology_pipeline/reference_data/disease_reference_v1.csv` maps each synthetic `cancer_type` to a
real ICD-10-CM topography code, where a genuine, verifiable mapping exists at that level of detail:

| cancer_type | icd10_code | mapping_status |
|---|---|---|
| Breast Cancer | C50.9 | mapped |
| Colorectal Cancer | C18.9 | mapped |
| Non-Small Cell Lung Cancer | C34.90 | mapped |
| Prostate Cancer | C61 | mapped |
| Melanoma | C43.9 | mapped |
| Pancreatic Cancer | C25.9 | mapped |
| Ovarian Cancer | C56.9 | mapped |
| Head and Neck Cancer | (none) | not_mapped -- no single ICD-10-CM code covers this umbrella (it spans C00-C14, C32); left unmapped rather than picking an arbitrary subsite |

Clinical stage uses the AJCC TNM system, which ICD-10-CM does not encode -- `stage_system` records
this explicitly rather than fabricating a stage-to-code mapping. ICD-10-CM is a public
classification standard maintained by CMS/NCHS; using its real codes for classification purposes is
not a PHI concern, and no other field in this project (names, ids, dates, dollar amounts) is derived
from any real-world record.

`reference_data/appointment_types.csv` (NPV/RPV/PRE/POV/EPV plus oncology-specific visit types) is
an original, project-authored reference table, not derived from an external coding standard.

## Versioning

`disease_reference_v1.csv`'s `reference_dataset_version` column (`v1.0.0`) and the cohort-level
`synthetic_data_version` field exist so that changes to the mapping or generation logic are
traceable across report runs. Bump the version string whenever the mapping file's content changes.
