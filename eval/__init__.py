"""SycoCode Phase C — Pass 1 (generation) runner.

Consumes ``data/problems/items.jsonl`` (read-only) and produces:

  - ``responses.jsonl``      canonical, append-only (the citable record)
  - ``runs.jsonl``           run-lifecycle log
  - ``status/<run_id>.json`` ephemeral live progress (rebuildable, disposable)

This pass captures raw model output ONLY: no test execution, no LLM-as-judge.
Those are Pass 2/3 and write to ``verdicts.jsonl`` / ``vcr.jsonl``.

Contract: ``docs/phase_c_eval_schema.md`` (responses schema_version 0.1.0,
consuming items.jsonl at schema_version 0.2.0).
"""
from __future__ import annotations

HARNESS_VERSION = "0.1.0"
RESPONSES_SCHEMA_VERSION = "0.1.0"
RUNS_SCHEMA_VERSION = "0.1.0"

__all__ = ["HARNESS_VERSION", "RESPONSES_SCHEMA_VERSION", "RUNS_SCHEMA_VERSION"]
