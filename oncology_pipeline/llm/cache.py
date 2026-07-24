"""Local, on-disk cache for successful LLM results.

Cache key = hash(model + prompt version + schema version + facts +
patient/cohort id). Never includes the API key.

Every read also validates the cached entry's recorded model, prompt
version, schema version, and supporting fact ids against what the current
run expects, deleting anything that fails. This is defense in depth beyond
the key match: it catches drift (e.g. --llm-model changed between runs)
that a key mismatch alone might miss, so stale or mismatched content is
never served as if it came from the configured model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def cache_key(model: str, packet: dict) -> str:
    payload = {
        "model": model,
        "prompt_version": packet["prompt_version"],
        "schema_version": packet["schema_version"],
        "subject_id": packet.get("patient_id") or packet.get("scope_id"),
        "facts": packet["facts"],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest


def _invalidate(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def get(
    cache_dir: Path, key: str, *, expected_model: str, expected_prompt_version: str,
    expected_schema_version: str, allowed_fact_ids: set[str],
) -> dict | None:
    """Returns the cached narrative dict, or None on any miss/mismatch.
    Any entry that fails validation is deleted so it stops being checked."""
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None

    try:
        envelope = json.loads(path.read_text())
    except json.JSONDecodeError:
        _invalidate(path)
        return None

    meta = envelope.get("meta", {})
    narrative = envelope.get("narrative")
    if narrative is None:
        _invalidate(path)
        return None

    if meta.get("model_name") != expected_model:
        _invalidate(path)
        return None
    if meta.get("prompt_version") != expected_prompt_version:
        _invalidate(path)
        return None
    if meta.get("schema_version") != expected_schema_version:
        _invalidate(path)
        return None

    fact_ids = narrative.get("supporting_fact_ids", [])
    if not all(fid in allowed_fact_ids for fid in fact_ids):
        _invalidate(path)
        return None

    return narrative


def put(cache_dir: Path, key: str, narrative: dict, *, model: str, prompt_version: str, schema_version: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "narrative": narrative,
        "meta": {"model_name": model, "prompt_version": prompt_version, "schema_version": schema_version},
    }
    path = cache_dir / f"{key}.json"
    path.write_text(json.dumps(envelope, indent=2))
