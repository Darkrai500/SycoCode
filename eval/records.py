"""Builders for the two canonical artifacts: responses.jsonl and runs.jsonl.

These encode the contract in docs/phase_c_eval_schema.md. Item facets are
denormalized VERBATIM from items.jsonl (0.2.0); the only derived ground-truth
field is ``bug_difficulty`` (L1/L2/L3 -> 1/2/3). ``expected_failing_tests`` is
intentionally NOT emitted (the oracle is Pass 2).
"""
from __future__ import annotations

from typing import List, Optional

from . import HARNESS_VERSION, RESPONSES_SCHEMA_VERSION, RUNS_SCHEMA_VERSION

_LEVEL_TO_DIFFICULTY = {"L1": 1, "L2": 2, "L3": 3}


def record_id(run_id: str, item_id: str) -> str:
    return f"{run_id}::{item_id}"


def bug_difficulty(bug_level: Optional[str]) -> Optional[int]:
    """Derived integer scale; None for the clean control (bug_level is None)."""
    if bug_level is None:
        return None
    return _LEVEL_TO_DIFFICULTY.get(bug_level)


def build_ground_truth(item: dict) -> dict:
    gt = item.get("ground_truth", {}) or {}
    return {
        "bug_present": gt.get("bug_present"),
        "bug_id": gt.get("bug_id"),
        "bug_category": gt.get("bug_category"),
        "bug_level": gt.get("bug_level"),
        "bug_difficulty": bug_difficulty(gt.get("bug_level")),
        "bug_description": gt.get("bug_description"),
    }


def build_response_record(*, item: dict, run_id: str, model_cfg, params,
                          transcript: List[dict], status: str,
                          error: Optional[dict], retries: int,
                          started_at: str, completed_at: str,
                          git_commit: str) -> dict:
    turns = (item.get("rendered_prompts", {}) or {}).get("turns", []) or []
    _ukeys = ("prompt_tokens", "completion_tokens", "total_tokens",
              "reasoning_tokens", "cached_tokens")
    usage_total = {k: 0 for k in _ukeys}
    usage_seen = {k: False for k in _ukeys}
    cost_total = 0.0
    cost_known = False
    for t in transcript:
        u = t.get("usage") or {}
        for k in usage_total:
            val = u.get(k)
            if val is not None:            # never fabricate 0 for an absent provider count
                usage_total[k] += int(val)
                usage_seen[k] = True
        if t.get("cost_usd") is not None:
            cost_total += t["cost_usd"]
            cost_known = True
    for k in usage_total:                  # unknown stays null, not a misleading 0
        if not usage_seen[k]:
            usage_total[k] = None
    rp = item.get("rendered_prompts", {}) or {}
    return {
        # identity & dataset linkage
        "schema_version": RESPONSES_SCHEMA_VERSION,
        "record_id": record_id(run_id, item["item_id"]),
        "run_id": run_id,
        "item_id": item["item_id"],
        "item_content_hash": item.get("content_hash"),
        # denormalized item facets (verbatim)
        "problem_ref": item.get("problem_ref"),
        "bug_ref": item.get("bug_ref"),
        "scenario_ref": item.get("scenario_ref"),
        "scenario_family": item.get("scenario_family"),
        "language": item.get("language"),
        "original_id": item.get("original_id"),
        "source": item.get("source"),
        "harness_kind": item.get("harness_kind"),
        "ground_truth": build_ground_truth(item),
        # model & request configuration
        "model": model_cfg.public_dict(),
        "request_params": params.record_dict(),
        # the interaction
        "system_prompt": rp.get("system"),
        "max_turns_configured": len(turns),
        "turns_executed": len(transcript),
        "transcript": transcript,
        # record-level status & accounting
        "status": status,
        "error": error,
        "retries": retries,
        "usage_total": usage_total,
        "cost_usd_total": round(cost_total, 8) if cost_known else None,
        "started_at": started_at,
        "completed_at": completed_at,
        # harness provenance
        "harness_version": HARNESS_VERSION,
        "git_commit": git_commit,
    }


def build_run_event(*, run_id: str, event: str, model_cfg, params,
                    items_path: str, items_hash: str, scope, scope_count: int,
                    counts: dict, status: str, concurrency: int,
                    started_at: str, updated_at: str, finished_at: Optional[str],
                    git_commit: str) -> dict:
    return {
        "schema_version": RUNS_SCHEMA_VERSION,
        "run_id": run_id,
        "event": event,                       # started | finished | aborted
        "model": model_cfg.public_dict(),
        "request_params": params.record_dict(),
        "dataset": {
            "items_path": items_path,
            "items_dataset_hash": items_hash,
            "scope_filter": scope.record_dict(),
        },
        "scope_item_count": scope_count,
        "counts": counts,                     # completed | failed | skipped_existing
        "status": status,                     # running | completed | failed | aborted
        "concurrency": concurrency,
        "started_at": started_at,
        "updated_at": updated_at,
        "finished_at": finished_at,
        "harness_version": HARNESS_VERSION,
        "git_commit": git_commit,
    }
