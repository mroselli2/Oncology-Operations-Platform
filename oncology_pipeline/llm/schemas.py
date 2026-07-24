"""Output schemas for the OpenRouter narrative layer.

Deliberately narrow: every field is either a restatement of a deterministic
fact or free-text narration of one, so the LLM can't introduce a number,
date, status, or recommendation the deterministic engine didn't compute.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

SCHEMA_VERSION = "v1"


class PatientCaseNarrative(BaseModel):
    patient_id: str
    operational_summary: str
    primary_bottleneck: str
    priority_rationale: str
    recommended_next_action: str
    internal_coordinator_note: str
    supporting_fact_ids: list[str]
    uncertainty_statement: str
    human_review_required: Literal[True]
    generated_by: Literal["openrouter_llm", "deterministic_template"]
    model_name: str

    @field_validator("human_review_required")
    @classmethod
    def _must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("human_review_required must be true")
        return v

    @field_validator("supporting_fact_ids")
    @classmethod
    def _non_empty_list(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("supporting_fact_ids must be a list")
        return v


class CohortSynthesisNarrative(BaseModel):
    scope_id: str  # "COHORT" or a facility/payer id for a scoped synthesis
    operational_summary: str
    key_patterns: str
    supporting_fact_ids: list[str]
    uncertainty_statement: str
    human_review_required: Literal[True]
    generated_by: Literal["openrouter_llm", "deterministic_template"]
    model_name: str

    @field_validator("human_review_required")
    @classmethod
    def _must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("human_review_required must be true")
        return v


def validate_supporting_fact_ids(fact_ids: list[str], allowed_fact_ids: set[str]) -> bool:
    """Every cited fact id must resolve to a fact the deterministic engine
    actually produced (see llm/fact_packet.py's `allowed_fact_ids`)."""
    return all(fid in allowed_fact_ids for fid in fact_ids)
