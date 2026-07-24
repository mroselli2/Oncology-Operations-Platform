import pytest
from pydantic import ValidationError

from oncology_pipeline.llm.schemas import PatientCaseNarrative, validate_supporting_fact_ids

VALID = {
    "patient_id": "ONC-PAT-000001",
    "operational_summary": "Summary.",
    "primary_bottleneck": "Imaging incomplete",
    "priority_rationale": "High priority given stage III.",
    "recommended_next_action": "Coordinate imaging completion.",
    "internal_coordinator_note": "Note.",
    "supporting_fact_ids": ["ONC-PAT-000001:risk_score"],
    "uncertainty_statement": "Based only on provided facts.",
    "human_review_required": True,
    "generated_by": "openrouter_llm",
    "model_name": "openai/gpt-oss-20b",
}


def test_valid_narrative_parses():
    model = PatientCaseNarrative(**VALID)
    assert model.human_review_required is True


def test_human_review_required_must_be_true():
    bad = {**VALID, "human_review_required": False}
    with pytest.raises(ValidationError):
        PatientCaseNarrative(**bad)


def test_generated_by_restricted_to_allowed_values():
    bad = {**VALID, "generated_by": "gpt-4"}
    with pytest.raises(ValidationError):
        PatientCaseNarrative(**bad)


def test_validate_supporting_fact_ids_accepts_known_ids():
    assert validate_supporting_fact_ids(["a", "b"], {"a", "b", "c"}) is True


def test_validate_supporting_fact_ids_rejects_unknown_ids():
    assert validate_supporting_fact_ids(["a", "z"], {"a", "b", "c"}) is False
