from oncology_pipeline.llm import cache

MODEL = "openai/gpt-oss-20b"
PROMPT_VERSION = "v2"
SCHEMA_VERSION = "v1"


def _packet():
    return {
        "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION, "patient_id": "ONC-PAT-000001",
        "facts": {"ONC-PAT-000001:risk_score": "80"},
        "allowed_fact_ids": ["ONC-PAT-000001:risk_score"],
    }


def _narrative(fact_ids=("ONC-PAT-000001:risk_score",)):
    return {"model_name": MODEL, "supporting_fact_ids": list(fact_ids), "hello": "world"}


def _get(tmp_path, key, **overrides):
    kwargs = dict(expected_model=MODEL, expected_prompt_version=PROMPT_VERSION,
                  expected_schema_version=SCHEMA_VERSION, allowed_fact_ids={"ONC-PAT-000001:risk_score"})
    kwargs.update(overrides)
    return cache.get(tmp_path, key, **kwargs)


def test_cache_key_is_stable():
    assert cache.cache_key(MODEL, _packet()) == cache.cache_key(MODEL, _packet())


def test_cache_key_changes_with_model():
    assert cache.cache_key(MODEL, _packet()) != cache.cache_key("model-b", _packet())


def test_cache_key_changes_with_facts():
    p1, p2 = _packet(), _packet()
    p2["facts"] = {"ONC-PAT-000001:risk_score": "99"}
    assert cache.cache_key(MODEL, p1) != cache.cache_key(MODEL, p2)


def test_cache_roundtrip_valid(tmp_path):
    key = cache.cache_key(MODEL, _packet())
    assert _get(tmp_path, key) is None
    cache.put(tmp_path, key, _narrative(), model=MODEL, prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION)
    result = _get(tmp_path, key)
    assert result is not None
    assert result["model_name"] == MODEL


def test_cache_rejects_model_mismatch(tmp_path):
    key = cache.cache_key(MODEL, _packet())
    cache.put(tmp_path, key, _narrative(), model=MODEL, prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION)
    # Entry written under one model, currently configured model differs
    result = _get(tmp_path, key, expected_model="gpt-4o")
    assert result is None
    assert not (tmp_path / f"{key}.json").exists()  # self-healed: stale entry deleted


def test_cache_rejects_prompt_version_mismatch(tmp_path):
    key = cache.cache_key(MODEL, _packet())
    cache.put(tmp_path, key, _narrative(), model=MODEL, prompt_version="v1", schema_version=SCHEMA_VERSION)
    result = _get(tmp_path, key, expected_prompt_version="v2")
    assert result is None


def test_cache_rejects_schema_version_mismatch(tmp_path):
    key = cache.cache_key(MODEL, _packet())
    cache.put(tmp_path, key, _narrative(), model=MODEL, prompt_version=PROMPT_VERSION, schema_version="v1")
    result = _get(tmp_path, key, expected_schema_version="v2")
    assert result is None


def test_cache_rejects_unresolvable_supporting_fact_ids(tmp_path):
    key = cache.cache_key(MODEL, _packet())
    cache.put(tmp_path, key, _narrative(fact_ids=["ONC-PAT-999999:not_real"]), model=MODEL,
              prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION)
    result = _get(tmp_path, key)
    assert result is None


def test_cache_never_contains_key_material(tmp_path):
    key = cache.cache_key(MODEL, _packet())
    cache.put(tmp_path, key, _narrative(), model=MODEL, prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION)
    raw = (tmp_path / f"{key}.json").read_text()
    assert "sk-" not in raw and "OPENROUTER_API_KEY" not in raw
