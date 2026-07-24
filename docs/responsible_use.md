# Responsible Use

## Synthetic data disclosure

Every record in this project is 100% synthetic. `dataset_type='synthetic'` and
`synthetic_data_version` are stamped on the patient table and run metadata. All identifiers use the
project's `ONC-*` namespace (`oncology_pipeline/identifiers.py`) with formats deliberately
non-standard so nothing here can be mistaken for a real MRN, NPI, TIN, CLIA number, or insurance
member id. The one real-world data source in the project is `reference_data/disease_reference_v1.csv`,
a versioned mapping to public ICD-10-CM topography codes (a public classification standard, not
PHI) -- applied only where a genuine, verifiable mapping exists; unmapped combinations are left
`mapping_status='not_mapped'` rather than assigned an invented code (see `docs/source_provenance.md`).

## LLM authority boundary

The LLM layer is a narrative and translation layer, not a decision-maker. It may summarize,
explain, and translate deterministic facts into coordinator-readable language. It may never:
compute a risk score, alter a pathway assignment, infer a clinical finding, interpret pathology or
biomarker results, determine slot or network eligibility, invent missing information, book an
appointment, send a message, contact a patient, or change a source record. Every LLM output is
schema-validated with `human_review_required` pinned to `true`.

## Secret handling

`OPENROUTER_API_KEY` (and the other keys present in `.env`) are loaded read-only via
`python-dotenv` and checked only for presence/non-emptiness (`config.has_openrouter_key()`). The
key value is never printed, logged, copied into another file, included in `.env.example`, stored in
the LLM cache, written to the usage ledger, or included in any generated report. `.env` is
git-ignored and is never opened in write mode by any code path in this project.

## Live-call discipline

Real OpenRouter calls are expensive to get wrong and are gated deliberately:

- The default automated test suite (`pytest`, no flags) makes **zero** network calls -- the sole
  network boundary (`llm.client._post_chat_completion`) is monkeypatched in every test.
- A `@pytest.mark.live` test is excluded from the default run (`pytest.ini`: `addopts = -m "not
  live"`) and must be explicitly requested (`pytest -m live`) **and separately authorized by the
  project owner** before it is ever executed -- it is not run automatically as part of "the tests
  pass."
- Every live call, including this project's own smoke-testing and diagnostic calls, is permanently
  recorded in `outputs/llm_usage_ledger.csv` and is not deleted or overwritten by subsequent runs.

### Incident record

On 2026-07-23/24, the first two live calls made during this project's own smoke testing both
returned content from `gpt-4o` instead of the configured `openai/gpt-oss-20b` -- see
`docs/architecture.md` for the full incident writeup, the fixes applied (request-level model
pinning, response-level mismatch rejection, cache invalidation), and their verification status. This
record is kept, not scrubbed, specifically so future maintainers can see that this exact failure
mode was observed once in production use, not just described as a theoretical risk.
