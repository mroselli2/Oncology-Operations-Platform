# Architecture

## Two layers, one authority boundary

**Deterministic intelligence layer** (`oncology_pipeline/generation`, `db`, `agents/*` except `llm_layer.py`):
synthetic data generation, pathway/milestone checks, interval calculations, risk scoring,
bottleneck detection, network/authorization checks, and slot matching. Everything a report or
narrative can say about a patient is computed here, in plain Python, before any LLM involvement.

**LLM-assisted communication layer** (`oncology_pipeline/llm/*`, `agents/llm_layer.py`, optional):
OpenRouter provides a schema-constrained language layer for up to 15 highest-priority case
narratives and one cohort-level synthesis per run. It may only summarize, explain, and translate
facts the deterministic layer already produced. It cannot compute a risk score, alter a pathway
assignment, infer a clinical finding, determine slot/network eligibility, or take any booking/
contact/write action. Every output row is stamped `generated_by` (`openrouter_llm` or
`deterministic_template`) and `human_review_required=true`.

## Module map

```
oncology_pipeline/
├── config.py              Settings + .env loading (read-only, never rewritten)
├── identifiers.py         ONC-* id formatters
├── generation/             cohort, patients, insurance, network, appointments, disease_reference
├── db/                      schema.sql, loader (rebuild-from-scratch), queries (typed reads)
├── agents/
│   ├── intake.py .. communication.py   the 5 deterministic agents (ported, unchanged logic)
│   ├── slot_matching.py                  deterministic ranking engine
│   ├── orchestrator.py                    runs the 5 agents + slot matching, writes agent_outputs
│   └── llm_layer.py                        optional narrative upgrade pass (Stage 3)
├── llm/
│   ├── schemas.py           Pydantic output contracts
│   ├── fact_packet.py       compact per-case/cohort fact packets (never raw tables)
│   ├── client.py             OpenRouter HTTP boundary, retry, model-mismatch guard
│   ├── cache.py               validated local cache
│   ├── budget.py               hard USD ceiling
│   └── ledger.py                outputs/llm_usage_ledger.csv writer
└── reports/                  Excel, Markdown, operational CSV/MD reports
```

## Incident: model substitution in the initial live smoke test (2026-07-23/24)

During the first live verification of the LLM layer, two successful calls (one patient-case
narrative, one cohort synthesis) both returned `model: "gpt-4o"` in the OpenRouter response body,
despite the request specifying `openai/gpt-oss-20b`. This is exactly the "silent fallback to a more
expensive model" failure mode the system is required to prevent, and it was caught by inspecting the
usage ledger's `actual_model` column rather than by any code-level assertion at the time — the
original client code accepted whatever content OpenRouter returned without checking which model
actually produced it.

**Root cause is not fully confirmed.** What was ruled out: a hardcoded string in this codebase
(none exists), an invalid/mistyped model slug (`openai/gpt-oss-20b` is a real, listed model in
OpenRouter's `/models` catalog), and a network/proxy stub (the connection to `openrouter.ai`
completed a genuine TLS handshake and returned real catalog data). The two leading remaining
hypotheses are an OpenRouter account-level default-fallback setting, or the `reasoning` request
parameter causing OpenRouter's own error-recovery routing to substitute a model. This was not
resolved with certainty because further live diagnostic calls were intentionally limited per the
project's live-call authorization discipline (see Responsible Use).

### Fixes applied (2026-07-24)

1. **Request-level pin**: every request now includes `"provider": {"allow_fallbacks": false}`,
   which should make OpenRouter return an error rather than silently routing to a different
   provider/model if the requested model can't serve the request as specified.
2. **Response-level verification (defense in depth)**: `client._call_with_one_retry` now compares
   the response's `model` field against the requested model on every call, before any content is
   parsed or trusted. A mismatch is treated as a hard failure (`model_substituted`) that goes
   straight to the deterministic-template fallback -- never retried, never accepted.
3. **Server-side model stamping**: the LLM's own self-reported `model_name` output field is no
   longer trusted for audit/cache purposes. After the response-level check passes, the verified
   `served_model` from the HTTP layer overwrites `parsed["model_name"]` before the result is cached
   or returned.
4. **Cache invalidation on mismatch**: see Cache Validation below -- a cache entry whose stored
   model doesn't match the currently configured model is rejected and deleted, not served.
5. **Prompt-version bump**: `PROMPT_VERSION` was bumped `v1 -> v2` because the request payload and
   response-trust logic materially changed (see `llm/fact_packet.py`). Since the cache key includes
   the prompt version, every entry written under the old, unguarded logic became unreachable by key
   as well as rejected by the validation check.

### Status at end of Stage 4

The two fixes above are verified via mocked tests (`tests/unit/test_llm_client_mocked.py::
test_response_from_different_model_is_rejected_as_fallback`,
`test_stale_cache_entry_from_different_model_is_not_served`). **A live call confirming the fix
resolves the original substitution has not yet been made.** One post-fix diagnostic live call was
made and it hit a *different* failure mode (`malformed_json`, from output truncation at the old
350-token cap -- see Token Truncation below) rather than confirming or refuting the model-pinning
fix. Do not treat this system as having live-confirmed the substitution fix until such a call
succeeds and its ledger row shows `actual_model` matching the configured model.

## Token truncation finding

The original `LLM_MAX_OUTPUT_TOKENS` default (350) was too tight for this schema: the post-fix
diagnostic call produced exactly 350 output tokens and failed JSON parsing, consistent with the
response being cut off mid-structure before the closing braces. The default has been raised to
**750** (`config.py`, `.env.example`). The hard dollar budget (`LLM_RUN_BUDGET_USD`, default $0.10)
is the real spending ceiling and is unaffected by this change -- token count and dollar cost are
independent controls, and raising the token ceiling does not relax the budget guard.

## Cache validation

`llm/cache.py` keys entries by `hash(model + prompt_version + schema_version + facts + subject_id)`,
but a key match alone was judged insufficient after the substitution incident -- a bumped
`PROMPT_VERSION` makes old entries unreachable, but doesn't protect against every future drift (e.g.
`--llm-model` changed between runs without a version bump, or manual edits to the cache directory).
`cache.get()` therefore additionally validates, on every read:

- the cached entry's recorded `model_name` matches the currently configured model,
- its `prompt_version` and `schema_version` match the current run's,
- every id in its `supporting_fact_ids` still resolves against the current run's
  `allowed_fact_ids`.

Any failed check causes the entry to be treated as a miss **and deleted** (self-healing), so a
stale or mismatched entry is checked and rejected at most once, not on every subsequent run.
