# Oncology Access and Care Coordination Platform

A fully synthetic reference implementation for examining oncology access, scheduling,
authorization, diagnostic prerequisites, capacity, and care-coordination workflows.

**Live App:** not yet deployed -- see [Running Locally](#running-locally) to run the dashboard on
your own machine in the meantime.

All data are synthetic. The platform does not make treatment decisions, book appointments, or send
patient communications.

## Contents

- [Dashboard Preview](#dashboard-preview)
- [What the Platform Does](#what-the-platform-does)
- [Operational Questions It Explores](#operational-questions-it-explores)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Running Locally](#running-locally)
- [Static Sample Outputs](#static-sample-outputs)
- [Testing](#testing)
- [Responsible Use](#responsible-use)
- [Limitations](#limitations)

## Dashboard Preview

Screenshots pending -- see `docs/assets/` once captured. The dashboard (`app/streamlit_app.py`) is a
read-only view over a published, committed data snapshot (`published_data/`) and requires no
API key or `.env` file to run.

## What the Platform Does

Models the operational problem of moving a synthetic patient from referral to definitive treatment
across branching care pathways, where delay is driven by real-world-shaped factors: incomplete
diagnostic workups, payer authorization turnaround, multidisciplinary review capacity,
facility/network constraints, and coordination bandwidth.

**Deterministic layer** -- generates a synthetic cohort (1,200 patients by default) across four
branching care pathways (Surgery-First, Neoadjuvant Therapy, Radiation-First, Systemic Therapy
Only), a relational network of facilities, payers, and service-specific in-network status and
capacity, and runs five deterministic agents (intake review, bottleneck detection, risk scoring,
recommendation, communication drafting) plus a capacity-aware slot-matching engine. This layer runs
entirely offline with zero external calls, and is authoritative over every score, bottleneck
classification, network determination, and slot recommendation the platform produces.

**LLM-assisted narrative layer (optional, bounded)** -- when enabled, a schema-constrained
OpenRouter call narrates up to 15 highest-risk cases plus one cohort-level synthesis, under a hard
dollar budget, with Pydantic-validated output and automatic fallback to deterministic templates on
any failure. This layer only summarizes, explains, and translates facts the deterministic layer
already computed. **It does not select treatment, interpret clinical findings, determine network or
slot eligibility, book appointments, or contact patients**, and every output is flagged as requiring
human review. See `docs/architecture.md` and `docs/methodology.md` for the full design, and
`docs/responsible_use.md` for the authority boundary in detail. The dashboard itself never calls
OpenRouter -- it only reads the published snapshot.

## Operational Questions It Explores

- Where in the referral-to-treatment pathway are patients getting stuck, and why?
- Which patients are highest-risk for further delay, and what's the single dominant driver?
- How large is the insurance-authorization backlog, and how is it distributed across payers?
- Which facilities have open capacity or cancellation slots that could pull a case forward?
- How is coordinator workload distributed, and where is it concentrated?

## Architecture

```
oncology_pipeline/     deterministic generation, database, agents, LLM layer, reports
app/streamlit_app.py   read-only dashboard over the published snapshot
scripts/                CLI entrypoint + snapshot/sample build scripts
published_data/          committed, read-only dashboard snapshot (baseline scenario, seed 42)
samples/                  curated static workbook + report generated from the snapshot
docs/                      architecture, methodology, data dictionary, responsible use
tests/                      offline unit/integration tests + one live-marked (opt-in) test
```

See `docs/architecture.md` for the deterministic-vs-LLM authority split and module map, and
`docs/methodology.md` for how pathways, scenarios, slot matching, and risk scoring work.

## Data Model

A SQLite database holds patients, referrals, providers, coordinators, facilities, payers and plans,
the payer-facility network, facility service capabilities, a normalized pathway-milestone chain,
appointments, encounters, diagnostic orders/results, authorizations, portal events, documents, agent
outputs, and (when enabled) LLM case narratives and slot recommendations. All identifiers use a
project-specific `ONC-*` namespace in non-standard formats, so nothing in the dataset can be mistaken
for a real MRN, NPI, TIN, CLIA number, or insurance member ID. See `docs/data_dictionary.md` for the
full schema and `docs/source_provenance.md` for what is generated versus derived from a real public
classification standard (ICD-10-CM topography codes, applied only where genuinely applicable).

Delay and capacity behavior is controlled by named, inspectable scenario presets
(`scenarios/scenario_configs.yaml`: `baseline`, `high_backlog`, `holiday_surge`) rather than
hardcoded constants, so cohort-level outcomes are explainable and reproducible run to run.

## Running Locally

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Dashboard (uses the committed published_data/ snapshot -- no .env or API key needed)
./.venv/bin/streamlit run app/streamlit_app.py

# Full pipeline (regenerates data/, requires no API key with --llm-mode off)
cp .env.example .env   # only needed if you want the optional LLM narrative layer
./.venv/bin/python scripts/run_pipeline.py --llm-mode off
```

### CLI flags (`scripts/run_pipeline.py`)

| Flag | Default | Purpose |
|---|---|---|
| `--llm-mode {auto,on,off}` | `auto` | `off`: never touches the network. `auto`: uses the LLM only if `OPENROUTER_API_KEY` is set. `on`: requires a key; falls back to deterministic templates on any failure. |
| `--scenario NAME` | `baseline` | Named delay/backlog preset from `scenarios/scenario_configs.yaml` (`baseline`, `high_backlog`, `holiday_surge`). |
| `--llm-max-cases N` | 15 | Max patient-level narrative calls per run. |
| `--llm-budget-usd X` | 0.10 | Hard per-run USD ceiling; `0.00` forces every case through the fallback path with zero network calls. |
| `--llm-model NAME` | `openai/gpt-oss-20b` | Overrides the fixed model (no automatic fallback to a different/pricier model is ever allowed). |
| `--refresh-llm-cache` | off | Bypasses the cache and forces fresh calls. |
| `--cohort-size N` | 1200 | Synthetic patient count. |

```bash
# off -- deterministic only, no network
python scripts/run_pipeline.py --llm-mode off

# zero-budget dry run -- exercises every guard rail, makes no network calls
python scripts/run_pipeline.py --llm-mode on --llm-budget-usd 0.00
```

Local pipeline runs write to `data/` and `outputs/` (both git-ignored, rebuilt from scratch each
run): `oncology_pipeline_analysis.xlsx`, `oncology_pipeline_report.md`, `slot_recommendations.csv`,
`huddle_queue.csv`, `portal_activity_report.csv`, `facility_network_report.csv`,
`payer_authorization_report.csv`, `coordinator_workload_report.csv`, and (when the LLM layer runs)
`llm_usage_ledger.csv`.

## Static Sample Outputs

For readers who don't want to run the app or pipeline:

- [`samples/oncology_operations_sample.xlsx`](samples/oncology_operations_sample.xlsx) -- cohort
  summary, daily huddle queue, high-risk cases, slot recommendations, facility summary, payer
  authorization summary, and a data dictionary.
- [`samples/oncology_operations_sample_report.md`](samples/oncology_operations_sample_report.md) --
  a short narrative summary of the same baseline snapshot.

Both are generated from the committed `published_data/` snapshot via `scripts/build_samples.py`.

## Testing

```bash
pytest              # offline only -- zero network access, the default and only automatic mode
pytest -m live       # makes real OpenRouter calls; requires separate authorization, see below
```

`pytest -m live` is excluded from the default collection (`pytest.ini`) and is never run as part of
normal development, CI, or automated verification. It must be explicitly requested and separately
authorized before use -- see `docs/responsible_use.md`.

## Responsible Use

- All data is fully synthetic; no real patient, provider, payer, or facility information is used or
  represented (`docs/responsible_use.md`, `docs/source_provenance.md`).
- The deterministic layer is authoritative over all risk scores, bottleneck classifications, network
  determinations, and slot recommendations; the optional LLM layer never computes or overrides them.
- All LLM-generated narrative content requires human review before operational use.
- The published dashboard is read-only: no write actions, no booking, no messaging, and no LLM calls
  from the app itself.

## Limitations

- **Known limitation (as of 2026-07-24):** the initial live verification of the OpenRouter layer
  returned content from a model other than the one configured (`gpt-4o` instead of
  `openai/gpt-oss-20b`). Fixes -- request-level model pinning, response-level mismatch rejection,
  and cache invalidation on model mismatch -- are implemented and verified via mocked tests, but
  have not yet been confirmed by a successful live call. See `docs/architecture.md` for the full
  technical writeup. Treat the LLM narrative layer as not yet live-verified until that confirmation
  occurs. This has no effect on the dashboard, which does not call the LLM layer.
- `scripts/legacy/` retains the two original standalone scripts this platform's data generation and
  authorization logic were consolidated from. They are superseded by `oncology_pipeline/` and kept
  for reference only; they should not be run.
