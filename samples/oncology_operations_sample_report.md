# Oncology Operations Sample Report

A curated sample of the deterministic operational analysis produced by the oncology operations pipeline, generated from the published baseline snapshot (scenario: baseline, seed: 42, 1,200 synthetic patients).

All data is fully synthetic. No real patient, provider, payer, or facility information is used or represented.

## Cohort Snapshot

- Patients analyzed: 1200
- High risk: 381  |  Delayed: 846

## Most Common Bottlenecks

- Imaging incomplete: 322 patients
- Pathology not received: 283 patients
- None identified: 263 patients
- Insurance authorization pending: 131 patients
- Biomarker/genomic testing not resolved: 92 patients
- Long overall projected diagnosis-to-treatment interval: 47 patients

## Pathway Distribution

- Surgery-First: 455 patients
- Neoadjuvant Therapy: 302 patients
- Systemic Therapy Only: 268 patients
- Radiation-First: 175 patients

## How to Read This Sample

- **Cohort Summary** -- aggregate counts and average risk by pathway, stage, payer type, and facility.
- **Daily Huddle Queue** -- the top active cases ranked by risk score, in the same shape the operational dashboard presents them.
- **High-Risk Cases** -- detail on the highest-risk patients, including the deterministic bottleneck and recommended action for each.
- **Slot Recommendations** -- ranked candidate appointment slots with the reason each ranking was assigned.
- **Facility Summary** -- service capacity and typical lead time by facility.
- **Payer Authorization** -- authorization volume and average phone time by payer and status.
- **Data Dictionary** -- field definitions for the sheets above.

## Scope

This sample reflects the deterministic layer only: risk scores, bottleneck classifications, and slot recommendations are computed in Python from the synthetic dataset. The platform also supports an optional, bounded LLM-assisted narrative layer for a small subset of cases; that layer is not represented in this static sample.
