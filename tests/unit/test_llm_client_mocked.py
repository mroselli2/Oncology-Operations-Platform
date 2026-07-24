"""Mocked OpenRouter client tests -- zero network access. The sole network
boundary (`client._post_chat_completion`) is monkeypatched in every test."""

from __future__ import annotations

import json

import pytest

from oncology_pipeline.config import Settings
from oncology_pipeline.llm import client as llm_client
from oncology_pipeline.llm.budget import BudgetGuard

PATIENT_ID = "ONC-PAT-000001"


def make_settings(**overrides) -> Settings:
    s = Settings(
        openrouter_model="openai/gpt-oss-20b",
        llm_max_output_tokens=350,
        llm_temperature=0.1,
        llm_reasoning_effort="low",
        llm_cache_enabled=True,
        refresh_llm_cache=False,
        llm_run_budget_usd=0.10,
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def make_packet():
    return {
        "prompt_version": "v1", "schema_version": "v1", "patient_id": PATIENT_ID,
        "facts": {f"{PATIENT_ID}:risk_score": "80", f"{PATIENT_ID}:primary_bottleneck": "Imaging incomplete"},
        "allowed_fact_ids": [f"{PATIENT_ID}:risk_score", f"{PATIENT_ID}:primary_bottleneck"],
    }


def valid_narrative_content():
    return json.dumps({
        "patient_id": PATIENT_ID,
        "operational_summary": "Imaging is incomplete, blocking further workup.",
        "primary_bottleneck": "Imaging incomplete",
        "priority_rationale": "Risk score 80 reflects missing imaging.",
        "recommended_next_action": "Coordinate imaging completion.",
        "internal_coordinator_note": "Please expedite imaging.",
        "supporting_fact_ids": [f"{PATIENT_ID}:risk_score", f"{PATIENT_ID}:primary_bottleneck"],
        "uncertainty_statement": "Based only on the provided deterministic facts.",
        "human_review_required": True,
        "generated_by": "openrouter_llm",
        "model_name": "openai/gpt-oss-20b",
    })


def ok_response(content: str, prompt_tokens=120, completion_tokens=90, reasoning_tokens=10, cost=0.0003):
    return {
        "ok": True, "status_code": 200, "content": content,
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                   "completion_tokens_details": {"reasoning_tokens": reasoning_tokens}, "cost": cost},
        "error_type": None, "model": "openai/gpt-oss-20b",
    }


def err_response(error_type: str, status_code=None):
    return {"ok": False, "status_code": status_code, "content": None, "usage": {}, "error_type": error_type, "model": None}


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-fake-not-real")
    yield


def _no_network_guard(monkeypatch):
    """Fails the test loudly if any test forgets to patch the network call."""
    def _boom(*a, **k):
        raise AssertionError("Real network call attempted in a mocked test")
    monkeypatch.setattr(llm_client, "_post_chat_completion", _boom)


# Valid response
def test_valid_response_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "_post_chat_completion", lambda payload, key: ok_response(valid_narrative_content()))
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t1", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "success"
    assert result.schema_validation_status == "valid"
    assert result.narrative["patient_id"] == PATIENT_ID
    assert result.input_tokens == 120 and result.output_tokens == 90 and result.reasoning_tokens == 10
    assert budget.calls_made == 1


# Malformed JSON, retried once, still malformed -> fallback
def test_malformed_json_falls_back_after_one_retry(tmp_path, monkeypatch):
    calls = {"n": 0}
    def fake_post(payload, key):
        calls["n"] += 1
        return ok_response("not valid json{{{")
    monkeypatch.setattr(llm_client, "_post_chat_completion", fake_post)
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t2", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "malformed_json"
    assert calls["n"] == 2  # initial + one retry, never more


# Schema failure (invalid field, e.g. human_review_required=False)
def test_schema_failure_falls_back(tmp_path, monkeypatch):
    bad = json.loads(valid_narrative_content())
    bad["human_review_required"] = False
    monkeypatch.setattr(llm_client, "_post_chat_completion", lambda payload, key: ok_response(json.dumps(bad)))
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t3", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "schema_invalid"
    assert result.schema_validation_status == "invalid"


def test_unsupported_fact_id_falls_back(tmp_path, monkeypatch):
    bad = json.loads(valid_narrative_content())
    bad["supporting_fact_ids"] = ["ONC-PAT-999999:not_a_real_fact"]
    monkeypatch.setattr(llm_client, "_post_chat_completion", lambda payload, key: ok_response(json.dumps(bad)))
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t3b", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "unsupported_fact_id"


# Timeout
def test_timeout_falls_back_without_retry(tmp_path, monkeypatch):
    calls = {"n": 0}
    def fake_post(payload, key):
        calls["n"] += 1
        return err_response("timeout")
    monkeypatch.setattr(llm_client, "_post_chat_completion", fake_post)
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t4", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "timeout"
    assert calls["n"] == 1  # transport errors are not retried


# Rate limiting
def test_rate_limited_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "_post_chat_completion", lambda payload, key: err_response("rate_limited", 429))
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t5", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "rate_limited"


# Unavailable model
def test_unavailable_model_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "_post_chat_completion", lambda payload, key: err_response("model_unavailable", 404))
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t6", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "model_unavailable"


# Missing key -- no network call should even be attempted
def test_missing_key_falls_back_with_no_network_call(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    _no_network_guard(monkeypatch)
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t7", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "missing_key"


# Cache hit -- no network call should be attempted
def test_cache_hit_makes_no_network_call(tmp_path, monkeypatch):
    from oncology_pipeline.llm import cache as cache_mod
    settings = make_settings()
    packet = make_packet()
    key = cache_mod.cache_key(settings.openrouter_model, packet)
    cache_mod.put(tmp_path, key, json.loads(valid_narrative_content()), model=settings.openrouter_model,
                  prompt_version=packet["prompt_version"], schema_version=packet["schema_version"])
    _no_network_guard(monkeypatch)
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, packet, {}, settings, budget, "run-t8", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "success"
    assert result.cache_hit is True
    assert budget.calls_made == 0  # cache hits never touch the budget


def test_stale_cache_entry_from_different_model_is_not_served(tmp_path, monkeypatch):
    """Regression test for the live incident where a cache entry written
    under a substituted model (gpt-4o) would otherwise keep being served."""
    from oncology_pipeline.llm import cache as cache_mod
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)  # ensures no real call even if wrongly served
    settings = make_settings()
    packet = make_packet()
    key = cache_mod.cache_key(settings.openrouter_model, packet)
    tainted = json.loads(valid_narrative_content())
    tainted["model_name"] = "gpt-4o"  # written as if a substituted model's response was cached
    cache_mod.put(tmp_path, key, tainted, model="gpt-4o",
                  prompt_version=packet["prompt_version"], schema_version=packet["schema_version"])
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, packet, {}, settings, budget, "run-t8b", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.cache_hit is False
    assert result.status == "fallback"
    assert result.fallback_reason == "missing_key"  # proves it fell through past the rejected cache entry
    assert not (tmp_path / f"{key}.json").exists()  # self-healed


# Budget exhaustion -- no network call should be attempted
def test_budget_exhaustion_falls_back_with_no_network_call(tmp_path, monkeypatch):
    _no_network_guard(monkeypatch)
    settings = make_settings()
    budget = BudgetGuard(budget_usd=0.0)  # exhausted from the start
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t9", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "budget_exceeded"


# Deterministic fallback template content, independent of the LLM client
def test_deterministic_template_fallback_content():
    from oncology_pipeline.agents import communication

    patient = {
        "mrn": "ONC-MRN-000001", "first_name": "Test", "last_name": "Patient",
        "diagnosis_type": "Breast Cancer", "stage": "II", "treatment_modality_pathway": "Surgery-First",
        "priority_level": "High", "payer_type": "Commercial", "scheduling_status": "Delayed",
        "assigned_coordinator_name": "Nina Alvarez",
    }
    intervals = {"primary_bottleneck": "Imaging incomplete"}
    risk = {"risk_level": "High", "risk_score": 80, "projected_days": 90}
    note = communication.draft(patient, intervals, risk, "Coordinate imaging completion.")
    assert "deterministic template" in note
    assert "Imaging incomplete" in note


# No silent fallback to a different/more expensive model
def test_requested_model_is_never_substituted(tmp_path, monkeypatch):
    captured_payloads = []
    def fake_post(payload, key):
        captured_payloads.append(payload)
        return ok_response(valid_narrative_content())
    monkeypatch.setattr(llm_client, "_post_chat_completion", fake_post)
    settings = make_settings(openrouter_model="openai/gpt-oss-20b")
    budget = BudgetGuard(budget_usd=0.10)
    llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t10", tmp_path, tmp_path / "ledger.csv",
    )
    assert all(p["model"] == "openai/gpt-oss-20b" for p in captured_payloads)
    assert all(p["provider"]["allow_fallbacks"] is False for p in captured_payloads)


def test_response_from_different_model_is_rejected_as_fallback(tmp_path, monkeypatch):
    """Guards against the live incident: content from an unrequested model
    must never be accepted as a successful narrative."""
    def fake_post(payload, key):
        resp = ok_response(valid_narrative_content())
        resp["model"] = "gpt-4o"  # a different, more expensive model than requested
        return resp
    monkeypatch.setattr(llm_client, "_post_chat_completion", fake_post)
    settings = make_settings(openrouter_model="openai/gpt-oss-20b")
    budget = BudgetGuard(budget_usd=0.10)
    result = llm_client.run_patient_case(
        None, PATIENT_ID, make_packet(), {}, settings, budget, "run-t11", tmp_path, tmp_path / "ledger.csv",
    )
    assert result.status == "fallback"
    assert result.fallback_reason == "model_substituted"
