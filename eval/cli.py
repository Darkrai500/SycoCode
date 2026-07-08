"""Command-line entrypoint: ``python -m eval [flags]``.

Config precedence: CLI flag > environment (SYCO_* / key var) > built-in default
(Cerebras gpt-oss-120b, Developer tier). The API key is read only from the
environment / .env, never from a flag.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import List, Optional

from .config import (ModelConfig, Paths, RateLimitConfig, RequestParams,
                     RetryConfig, RunConfig, ScopeFilter, load_dotenv)
from .runner import run


def _csv(val: Optional[str]) -> Optional[List[str]]:
    if val is None:
        return None
    parts = [x.strip() for x in val.split(",") if x.strip()]
    return parts or None


def _env_or(default, *names, cast=str):
    for n in names:
        v = os.environ.get(n)
        if v is not None and v != "":
            try:
                return cast(v)
            except (TypeError, ValueError):
                pass
    return default


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval",
        description="SycoCode Phase C — Pass 1 generation runner (no judgment).",
    )
    p.add_argument("--items", default=None, help="path to items.jsonl (read-only)")
    p.add_argument("--out-dir", default=None, help="output dir for responses/runs/status")

    p.add_argument("--scope-problem", default=None,
                   help="comma-separated problem_refs, e.g. cand_001 (omit = ALL 50)")
    p.add_argument("--scope-scenario", default=None, help="comma-separated scenario_refs")
    p.add_argument("--scope-language", default=None, help="en,es")
    p.add_argument("--limit", type=int, default=None, help="cap number of items (e.g. 1)")

    p.add_argument("--provider", default=None)
    p.add_argument("--base-url", default=None)
    p.add_argument("--model", default=None, help="api_model_id, e.g. gpt-oss-120b")
    p.add_argument("--logical-name", default=None)
    p.add_argument("--api-key-var", default=None, help="env var holding the key")
    p.add_argument("--max-tokens-param", default=None,
                   help="wire param name (cerebras: max_completion_tokens)")

    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--top-p", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--seed", default=None, help="integer, or 'none' to omit seed")

    p.add_argument("--concurrency", type=int, default=None)
    p.add_argument("--rpm", type=float, default=None, help="requests/min (<=0 disables)")
    p.add_argument("--tpm", type=float, default=None, help="tokens/min (<=0 disables)")

    p.add_argument("--max-retries", type=int, default=None)
    p.add_argument("--timeout", type=float, default=None, help="per-request timeout (s)")
    p.add_argument("--fail-fast-after", type=int, default=None,
                   help="abort after N consecutive item failures (0 disables; default 30)")

    p.add_argument("--resume", default=None, metavar="RUN_ID",
                   help="resume a run: skip its already-completed items")
    p.add_argument("--dry-run", action="store_true",
                   help="report scope/coverage and exit; no API calls")
    p.add_argument("--progress", default=None, choices=["auto", "rich", "plain", "none"],
                   help="terminal progress on stderr (default: $SYCO_PROGRESS or auto; "
                        "stdout stays reserved for the final JSON summary)")
    p.add_argument("--env-file", default=".env")
    return p


def _resolve_seed(args) -> Optional[int]:
    raw = args.seed if args.seed is not None else os.environ.get("SYCO_SEED", "7")
    if raw is None or str(raw).strip().lower() in ("none", "null", ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def build_config(args) -> RunConfig:
    model = ModelConfig(
        logical_name=args.logical_name or _env_or("gpt-oss", "SYCO_LOGICAL_NAME"),
        provider=args.provider or _env_or("cerebras", "SYCO_PROVIDER"),
        api_model_id=args.model or _env_or("gpt-oss-120b", "SYCO_API_MODEL_ID"),
        base_url=args.base_url or _env_or("https://api.cerebras.ai/v1", "SYCO_BASE_URL"),
        api_key_var=args.api_key_var or _env_or("CEREBRAS_API_KEY", "SYCO_API_KEY_VAR"),
        max_tokens_param=(args.max_tokens_param
                          or _env_or("max_completion_tokens", "SYCO_MAX_TOKENS_PARAM")),
    )
    params = RequestParams(
        temperature=(args.temperature if args.temperature is not None
                     else _env_or(0.0, "SYCO_TEMPERATURE", cast=float)),
        top_p=(args.top_p if args.top_p is not None
               else _env_or(1.0, "SYCO_TOP_P", cast=float)),
        max_tokens=(args.max_tokens if args.max_tokens is not None
                    else _env_or(8192, "SYCO_MAX_TOKENS", cast=int)),
        seed=_resolve_seed(args),
    )
    retry = RetryConfig(
        max_retries=(args.max_retries if args.max_retries is not None
                     else _env_or(6, "SYCO_MAX_RETRIES", cast=int)),
        request_timeout_s=(args.timeout if args.timeout is not None
                           else _env_or(120.0, "SYCO_TIMEOUT", cast=float)),
        fail_fast_after=(args.fail_fast_after if args.fail_fast_after is not None
                         else _env_or(30, "SYCO_FAIL_FAST_AFTER", cast=int)),
    )
    rate = RateLimitConfig(
        concurrency=(args.concurrency if args.concurrency is not None
                     else _env_or(12, "SYCO_CONCURRENCY", cast=int)),
        rpm=(args.rpm if args.rpm is not None else _env_or(1000.0, "SYCO_RPM", cast=float)),
        tpm=(args.tpm if args.tpm is not None else _env_or(1_000_000.0, "SYCO_TPM", cast=float)),
    )
    scope = ScopeFilter(
        problem_refs=_csv(args.scope_problem),
        scenarios=_csv(args.scope_scenario),
        languages=_csv(args.scope_language),
        limit=args.limit,
    )
    paths = Paths(
        items_path=args.items or _env_or("data/problems/items.jsonl", "SYCO_ITEMS_PATH"),
        out_dir=args.out_dir or _env_or("data/runs", "SYCO_OUT_DIR"),
    )
    return RunConfig(model=model, params=params, retry=retry, rate=rate,
                     scope=scope, paths=paths, resume_run_id=args.resume,
                     dry_run=args.dry_run,
                     progress_mode=args.progress or _env_or("auto", "SYCO_PROGRESS"))


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    load_dotenv(args.env_file)
    cfg = build_config(args)
    try:
        summary = asyncio.run(run(cfg))
    except KeyboardInterrupt:
        # asyncio.run already cancelled the run task (which wrote an 'aborted'
        # event in its finally); just exit quietly without a raw traceback.
        print('{"status": "aborted", "reason": "interrupted"}')
        return
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
