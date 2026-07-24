"""Settings and .env loading. .env is loaded read-only and never rewritten.

Never print, log, or otherwise surface the value of any *_API_KEY/*_TOKEN var.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)  # read-only

_SECRET_SUFFIXES = ("_API_KEY", "_TOKEN")


def _is_secret_name(name: str) -> bool:
    return any(name.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def has_openrouter_key() -> bool:
    """Presence/non-empty check only -- never returns or logs the value."""
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val not in (None, "") else default


@dataclass
class Settings:
    llm_mode: str = "auto"                 # auto | on | off
    scenario_name: str = "baseline"
    openrouter_model: str = "openai/gpt-oss-20b"
    openrouter_free_model: str = "openai/gpt-oss-20b:free"
    llm_max_cases: int = 15
    llm_max_calls_per_run: int = 17
    llm_max_output_tokens: int = 750
    llm_temperature: float = 0.1
    llm_run_budget_usd: float = 0.10
    llm_cache_enabled: bool = True
    llm_allow_model_fallback: bool = False
    llm_reasoning_effort: str = "low"
    refresh_llm_cache: bool = False
    cohort_size: int = 1200
    random_seed: int = 42
    run_id: str = "run-001"

    db_path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "oncology_pipeline.db")
    cache_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "cache" / "llm")
    outputs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "outputs")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_mode=os.environ.get("LLM_MODE", "auto"),
            openrouter_model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b"),
            openrouter_free_model=os.environ.get("OPENROUTER_FREE_MODEL", "openai/gpt-oss-20b:free"),
            llm_max_cases=_env_int("LLM_MAX_CASES", 15),
            llm_max_calls_per_run=_env_int("LLM_MAX_CALLS_PER_RUN", 17),
            llm_max_output_tokens=_env_int("LLM_MAX_OUTPUT_TOKENS", 750),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.1),
            llm_run_budget_usd=_env_float("LLM_RUN_BUDGET_USD", 0.10),
            llm_cache_enabled=_env_bool("LLM_CACHE_ENABLED", True),
            llm_allow_model_fallback=_env_bool("LLM_ALLOW_MODEL_FALLBACK", False),
            llm_reasoning_effort=os.environ.get("LLM_REASONING_EFFORT", "low"),
        )

    def apply_cli_overrides(self, **overrides) -> "Settings":
        for key, value in overrides.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)
        return self
