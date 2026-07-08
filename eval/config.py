"""Runner configuration.

Secrets (API keys) come from the environment / ``.env`` ONLY and are never
stored in records. Everything else has Cerebras + Developer-tier defaults that
are overridable by env (``SYCO_*``) and then by CLI flags (see ``cli.py``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def load_dotenv(path: str = ".env") -> None:
    """Minimal ``.env`` loader: ``KEY=VALUE`` lines. Does NOT override variables
    already present in the environment. Supports ``#`` comments and quoted values."""
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


@dataclass
class ModelConfig:
    logical_name: str = "gpt-oss"
    provider: str = "cerebras"
    api_model_id: str = "gpt-oss-120b"
    base_url: str = "https://api.cerebras.ai/v1"
    api_key_var: str = "CEREBRAS_API_KEY"
    # Cerebras chat/completions wants max_completion_tokens; OpenRouter wants max_tokens.
    max_tokens_param: str = "max_completion_tokens"

    def public_dict(self) -> dict:
        """The ``model`` block stored in records — never includes the API key."""
        return {
            "logical_name": self.logical_name,
            "provider": self.provider,
            "api_model_id": self.api_model_id,
            "base_url": self.base_url,
        }


@dataclass
class RequestParams:
    temperature: float = 0.0
    top_p: float = 1.0
    # 8192: gpt-oss-120b is a reasoning model — it spends tokens on a hidden
    # reasoning channel before the final answer, so a small cap truncates the
    # answer (finish_reason=length, content=null). Billed per actual token.
    max_tokens: int = 8192        # logical cap; wire name set by ModelConfig.max_tokens_param
    seed: Optional[int] = 7       # Cerebras honors seed best-effort; None omits it
    # reasoning models only: "low"|"medium"|"high". None omits it. Sent on the wire
    # but NOT recorded in request_params (keeps the Pass-1 responses schema stable).
    reasoning_effort: Optional[str] = None

    def record_dict(self) -> dict:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
        }


@dataclass
class RetryConfig:
    max_retries: int = 6
    backoff_base_s: float = 2.0
    backoff_cap_s: float = 60.0
    request_timeout_s: float = 120.0
    # Circuit breaker: abort the run after this many CONSECUTIVE item failures
    # with no success in between (a strong signal the endpoint is down, not a
    # blip). Reset by any completed item. 0 disables.
    fail_fast_after: int = 30


@dataclass
class RateLimitConfig:
    concurrency: int = 12          # concurrent items (a 5-turn item holds one slot)
    rpm: float = 1000.0            # requests/min; <= 0 disables the bucket
    tpm: float = 1_000_000.0       # tokens/min; <= 0 disables the bucket


@dataclass
class ScopeFilter:
    problem_refs: Optional[List[str]] = None
    scenarios: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    limit: Optional[int] = None

    def record_dict(self) -> dict:
        return {
            "scenarios": self.scenarios,
            "languages": self.languages,
            "problem_refs": self.problem_refs,
        }


@dataclass
class Paths:
    items_path: str = "data/problems/items.jsonl"
    out_dir: str = "data/runs"

    @property
    def responses_path(self) -> str:
        return str(Path(self.out_dir) / "responses.jsonl")

    @property
    def runs_path(self) -> str:
        return str(Path(self.out_dir) / "runs.jsonl")

    @property
    def status_dir(self) -> str:
        return str(Path(self.out_dir) / "status")


@dataclass
class RunConfig:
    model: ModelConfig
    params: RequestParams
    retry: RetryConfig
    rate: RateLimitConfig
    scope: ScopeFilter
    paths: Paths
    resume_run_id: Optional[str] = None
    dry_run: bool = False
    # Terminal progress on stderr (see eval/progress.py): auto|rich|plain|none.
    # "auto" picks rich on a TTY and degrades to plain otherwise.
    progress_mode: str = "auto"

    def resolve_api_key(self) -> str:
        key = os.environ.get(self.model.api_key_var, "").strip()
        if not key:
            raise SystemExit(
                f"Missing API key: set {self.model.api_key_var} in your environment "
                f"or in .env (see .env.example)."
            )
        return key
