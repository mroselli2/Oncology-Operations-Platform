"""Appends one row per attempted LLM request (including cache hits and
fallbacks) to outputs/llm_usage_ledger.csv. Never stores the API key,
auth headers, or full raw prompts/responses."""

from __future__ import annotations

import csv
from pathlib import Path

LEDGER_COLUMNS = [
    "run_id", "timestamp", "request_type", "patient_or_cohort_id",
    "requested_model", "actual_model", "prompt_version",
    "input_tokens", "output_tokens", "reasoning_tokens",
    "cache_hit", "retry_count", "reported_cost", "cumulative_run_cost",
    "success_or_fallback_status", "fallback_reason", "schema_validation_status",
]


def append_row(ledger_path: Path, row: dict) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = ledger_path.exists()
    with open(ledger_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({col: row.get(col, "") for col in LEDGER_COLUMNS})


def summarize(ledger_path: Path, run_id: str) -> dict:
    if not ledger_path.exists():
        return {"api_calls": 0, "cache_hits": 0, "fallbacks": 0, "total_cost": 0.0}
    api_calls = cache_hits = fallbacks = 0
    total_cost = 0.0
    with open(ledger_path, newline="") as f:
        for row in csv.DictReader(f):
            if row["run_id"] != run_id:
                continue
            if row["cache_hit"] == "True":
                cache_hits += 1
            elif row["success_or_fallback_status"] == "success":
                api_calls += 1
            elif row["success_or_fallback_status"] == "fallback":
                fallbacks += 1
            try:
                total_cost += float(row["reported_cost"] or 0)
            except ValueError:
                pass
    return {"api_calls": api_calls, "cache_hits": cache_hits, "fallbacks": fallbacks, "total_cost": total_cost}
