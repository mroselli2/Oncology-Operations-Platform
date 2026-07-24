"""OpenRouter client: one fixed, inexpensive model, one retry on malformed/
invalid output, no silent fallback to a different or pricier model ever.

The low-level `_post_chat_completion` is the sole network boundary and is
what tests monkeypatch to simulate every failure mode without live calls.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from pydantic import ValidationError

from . import budget as budget_mod
from . import cache as cache_mod
from . import ledger as ledger_mod
from .schemas import CohortSynthesisNarrative, PatientCaseNarrative, validate_supporting_fact_ids

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 20

PATIENT_SYSTEM_PROMPT = (
    "You are a clinical operations narration assistant. You will be given a JSON packet of "
    "already-computed deterministic facts about one synthetic oncology patient. Your ONLY job is to "
    "summarize, explain, and translate those facts into readable coordinator language. "
    "Rules: never invent a date, status, facility, clinical finding, or recommendation not present "
    "in the facts you were given. The 'recommended_next_action' field must restate the "
    "deterministic_recommended_action fact, not propose a new one. Every id in supporting_fact_ids "
    "must be copied verbatim from the packet's allowed_fact_ids list. human_review_required must "
    "always be true. generated_by must be 'openrouter_llm'. Respond with ONLY a single JSON object "
    "matching this exact shape (no markdown, no prose outside the JSON):\n"
    '{"patient_id": str, "operational_summary": str, "primary_bottleneck": str, '
    '"priority_rationale": str, "recommended_next_action": str, "internal_coordinator_note": str, '
    '"supporting_fact_ids": [str], "uncertainty_statement": str, "human_review_required": true, '
    '"generated_by": "openrouter_llm", "model_name": str}'
)

COHORT_SYSTEM_PROMPT = (
    "You are a clinical operations narration assistant. You will be given a JSON packet of "
    "already-computed deterministic cohort-level statistics for a synthetic oncology scheduling "
    "program. Summarize the patterns for a daily-huddle audience. Never invent a number or pattern "
    "not present in the facts. Every id in supporting_fact_ids must be copied verbatim from the "
    "packet's allowed_fact_ids list. human_review_required must always be true. generated_by must "
    "be 'openrouter_llm'. Respond with ONLY a single JSON object matching this exact shape:\n"
    '{"scope_id": str, "operational_summary": str, "key_patterns": str, '
    '"supporting_fact_ids": [str], "uncertainty_statement": str, "human_review_required": true, '
    '"generated_by": "openrouter_llm", "model_name": str}'
)


@dataclass
class LLMCallResult:
    status: str  # "success" | "fallback"
    fallback_reason: str | None = None
    narrative: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    actual_model: str | None = None
    retry_count: int = 0
    schema_validation_status: str = "not_attempted"
    cache_hit: bool = False


def _post_chat_completion(payload: dict, api_key: str) -> dict:
    """Sole network boundary. Returns a normalized dict:
    {"ok": bool, "status_code": int|None, "content": str|None, "usage": dict,
     "error_type": str|None, "model": str|None}
    Never raises for expected failure modes -- callers branch on error_type."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        return {"ok": False, "status_code": None, "content": None, "usage": {}, "error_type": "timeout", "model": None}
    except requests.exceptions.RequestException:
        return {"ok": False, "status_code": None, "content": None, "usage": {}, "error_type": "network_error", "model": None}

    if resp.status_code == 401:
        return {"ok": False, "status_code": 401, "content": None, "usage": {}, "error_type": "missing_key", "model": None}
    if resp.status_code == 429:
        return {"ok": False, "status_code": 429, "content": None, "usage": {}, "error_type": "rate_limited", "model": None}
    if resp.status_code == 404:
        return {"ok": False, "status_code": 404, "content": None, "usage": {}, "error_type": "model_unavailable", "model": None}
    if resp.status_code >= 400:
        return {"ok": False, "status_code": resp.status_code, "content": None, "usage": {}, "error_type": "api_error", "model": None}

    try:
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        model = body.get("model")
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return {"ok": False, "status_code": resp.status_code, "content": None, "usage": {}, "error_type": "malformed_response", "model": None}

    return {"ok": True, "status_code": resp.status_code, "content": content, "usage": usage, "error_type": None, "model": model}


def _build_payload(system_prompt: str, user_content: dict, model: str, settings) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content)},
        ],
        "max_tokens": settings.llm_max_output_tokens,
        "temperature": settings.llm_temperature,
        "reasoning": {"effort": settings.llm_reasoning_effort},
        # Never let OpenRouter silently route to a different model/provider;
        # an unservable request should error (-> deterministic fallback),
        # not substitute.
        "provider": {"allow_fallbacks": False},
    }


def _extract_usage(usage: dict) -> tuple[int, int, int, float]:
    input_tokens = int(usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(usage.get("completion_tokens", 0) or 0)
    reasoning_tokens = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0)
    cost = float(usage.get("cost", 0.0) or 0.0)
    return input_tokens, output_tokens, reasoning_tokens, cost


def _log_and_return(
    ledger_path: Path, run_id: str, request_type: str, subject_id: str, settings,
    result: LLMCallResult, cumulative_run_cost: float = 0.0,
) -> LLMCallResult:
    ledger_mod.append_row(ledger_path, {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_type": request_type,
        "patient_or_cohort_id": subject_id,
        "requested_model": settings.openrouter_model,
        "actual_model": result.actual_model or "",
        "prompt_version": "v1",
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "cache_hit": result.cache_hit,
        "retry_count": result.retry_count,
        "reported_cost": result.cost_usd,
        "cumulative_run_cost": cumulative_run_cost,
        "success_or_fallback_status": result.status,
        "fallback_reason": result.fallback_reason or "",
        "schema_validation_status": result.schema_validation_status,
    })
    return result


def _call_with_one_retry(
    system_prompt: str, packet: dict, schema_cls, model: str, settings,
) -> tuple[str, dict | None, dict, int, str, str | None]:
    """Returns (outcome, parsed_dict_or_None, raw_usage, retry_count, schema_status, served_model).
    outcome in: success | timeout | rate_limited | model_unavailable | missing_key |
    network_error | api_error | malformed_json | schema_invalid | unsupported_fact_id |
    model_substituted. `served_model` is whatever OpenRouter reported in the response
    (even on failure), for audit purposes -- never used to accept a result."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    payload = _build_payload(system_prompt, packet, model, settings)

    for attempt in range(2):  # initial attempt + at most 1 retry
        resp = _post_chat_completion(payload, api_key)
        if not resp["ok"]:
            if resp["error_type"] in ("timeout", "rate_limited", "model_unavailable", "missing_key", "network_error", "api_error"):
                return resp["error_type"], None, resp.get("usage", {}), attempt, "not_attempted", resp.get("model")
            return "api_error", None, {}, attempt, "not_attempted", resp.get("model")

        # Defense in depth on top of allow_fallbacks=false: reject content
        # from any model other than the one requested.
        if resp.get("model") and resp["model"] != model:
            return "model_substituted", None, resp.get("usage", {}), attempt, "not_attempted", resp.get("model")

        try:
            parsed_json = json.loads(resp["content"])
        except json.JSONDecodeError:
            if attempt == 0:
                continue
            return "malformed_json", None, resp["usage"], attempt, "invalid", resp.get("model")

        try:
            model_obj = schema_cls(**parsed_json)
        except ValidationError:
            if attempt == 0:
                continue
            return "schema_invalid", None, resp["usage"], attempt, "invalid", resp.get("model")

        allowed = set(packet["allowed_fact_ids"])
        if not validate_supporting_fact_ids(model_obj.supporting_fact_ids, allowed):
            if attempt == 0:
                continue
            return "unsupported_fact_id", None, resp["usage"], attempt, "invalid", resp.get("model")

        return "success", model_obj.model_dump(), resp["usage"], attempt, "valid", resp.get("model")

    return "malformed_json", None, {}, 1, "invalid", None


def _fallback_result(reason: str, retry_count: int = 0) -> LLMCallResult:
    return LLMCallResult(status="fallback", fallback_reason=reason, retry_count=retry_count,
                          schema_validation_status="not_attempted" if reason not in ("schema_invalid", "unsupported_fact_id") else "invalid")


def run_patient_case(
    conn, patient_id: str, packet: dict, agent_output_row: dict, settings, budget: budget_mod.BudgetGuard,
    run_id: str, cache_dir: Path, ledger_path: Path,
) -> LLMCallResult:
    key = cache_mod.cache_key(settings.openrouter_model, packet)
    if settings.llm_cache_enabled and not settings.refresh_llm_cache:
        cached = cache_mod.get(
            cache_dir, key, expected_model=settings.openrouter_model,
            expected_prompt_version=packet["prompt_version"], expected_schema_version=packet["schema_version"],
            allowed_fact_ids=set(packet["allowed_fact_ids"]),
        )
        if cached is not None:
            result = LLMCallResult(status="success", narrative=cached, cache_hit=True,
                                    actual_model=cached.get("model_name"), schema_validation_status="valid")
            return _log_and_return(ledger_path, run_id, "patient_case", patient_id, settings, result, budget.spent_usd)

    if not os_env_has_key():
        result = _fallback_result("missing_key")
        return _log_and_return(ledger_path, run_id, "patient_case", patient_id, settings, result, budget.spent_usd)

    can_afford, reason = budget.can_afford_another_call()
    if not can_afford:
        result = _fallback_result(reason)
        return _log_and_return(ledger_path, run_id, "patient_case", patient_id, settings, result, budget.spent_usd)

    outcome, parsed, usage, retry_count, schema_status, served_model = _call_with_one_retry(
        PATIENT_SYSTEM_PROMPT, packet, PatientCaseNarrative, settings.openrouter_model, settings,
    )
    input_tokens, output_tokens, reasoning_tokens, cost = _extract_usage(usage)

    if outcome != "success":
        result = LLMCallResult(status="fallback", fallback_reason=outcome, retry_count=retry_count,
                                input_tokens=input_tokens, output_tokens=output_tokens,
                                reasoning_tokens=reasoning_tokens, cost_usd=cost,
                                schema_validation_status=schema_status, actual_model=served_model)
        budget.record_actual_cost(cost)
        return _log_and_return(ledger_path, run_id, "patient_case", patient_id, settings, result, budget.spent_usd)

    # served_model (already verified against the request) is authoritative,
    # not the model's own self-reported model_name field.
    parsed["model_name"] = served_model
    budget.record_actual_cost(cost)
    if settings.llm_cache_enabled:
        cache_mod.put(cache_dir, key, parsed, model=settings.openrouter_model,
                       prompt_version=packet["prompt_version"], schema_version=packet["schema_version"])

    result = LLMCallResult(status="success", narrative=parsed, input_tokens=input_tokens,
                            output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
                            cost_usd=cost, actual_model=served_model,
                            retry_count=retry_count, schema_validation_status="valid")
    return _log_and_return(ledger_path, run_id, "patient_case", patient_id, settings, result, budget.spent_usd)


def run_cohort_synthesis(
    conn, packet: dict, settings, budget: budget_mod.BudgetGuard, run_id: str, cache_dir: Path, ledger_path: Path,
) -> LLMCallResult:
    key = cache_mod.cache_key(settings.openrouter_model, packet)
    if settings.llm_cache_enabled and not settings.refresh_llm_cache:
        cached = cache_mod.get(
            cache_dir, key, expected_model=settings.openrouter_model,
            expected_prompt_version=packet["prompt_version"], expected_schema_version=packet["schema_version"],
            allowed_fact_ids=set(packet["allowed_fact_ids"]),
        )
        if cached is not None:
            result = LLMCallResult(status="success", narrative=cached, cache_hit=True,
                                    actual_model=cached.get("model_name"), schema_validation_status="valid")
            return _log_and_return(ledger_path, run_id, "cohort_synthesis", "COHORT", settings, result, budget.spent_usd)

    if not os_env_has_key():
        result = _fallback_result("missing_key")
        return _log_and_return(ledger_path, run_id, "cohort_synthesis", "COHORT", settings, result, budget.spent_usd)

    can_afford, reason = budget.can_afford_another_call()
    if not can_afford:
        result = _fallback_result(reason)
        return _log_and_return(ledger_path, run_id, "cohort_synthesis", "COHORT", settings, result, budget.spent_usd)

    outcome, parsed, usage, retry_count, schema_status, served_model = _call_with_one_retry(
        COHORT_SYSTEM_PROMPT, packet, CohortSynthesisNarrative, settings.openrouter_model, settings,
    )
    input_tokens, output_tokens, reasoning_tokens, cost = _extract_usage(usage)

    if outcome != "success":
        result = LLMCallResult(status="fallback", fallback_reason=outcome, retry_count=retry_count,
                                input_tokens=input_tokens, output_tokens=output_tokens,
                                reasoning_tokens=reasoning_tokens, cost_usd=cost,
                                schema_validation_status=schema_status, actual_model=served_model)
        budget.record_actual_cost(cost)
        return _log_and_return(ledger_path, run_id, "cohort_synthesis", "COHORT", settings, result, budget.spent_usd)

    parsed["model_name"] = served_model
    budget.record_actual_cost(cost)
    if settings.llm_cache_enabled:
        cache_mod.put(cache_dir, key, parsed, model=settings.openrouter_model,
                       prompt_version=packet["prompt_version"], schema_version=packet["schema_version"])

    result = LLMCallResult(status="success", narrative=parsed, input_tokens=input_tokens,
                            output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
                            cost_usd=cost, actual_model=parsed.get("model_name") or settings.openrouter_model,
                            retry_count=retry_count, schema_validation_status="valid")
    return _log_and_return(ledger_path, run_id, "cohort_synthesis", "COHORT", settings, result, budget.spent_usd)


def os_env_has_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
