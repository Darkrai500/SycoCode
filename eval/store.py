"""Persistence: append-only JSONL writers, resume index, live status file.

``responses.jsonl`` / ``runs.jsonl`` are append-only and never mutated. The
status file is the only mutable artifact and is rewritten atomically.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from pathlib import Path
from typing import Optional, Set

from .progress import RunStats


def completed_record_ids(responses_path: str, run_id: str) -> Set[str]:
    """Resume index: record_ids already 'completed' for this run (skip them)."""
    done: Set[str] = set()
    p = Path(responses_path)
    if not p.is_file():
        return done
    with p.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("run_id") == run_id and rec.get("status") == "completed":
                rid = rec.get("record_id")
                if rid:
                    done.add(rid)
    return done


def seed_run_stats(responses_path: str, run_id: str, stats: RunStats) -> None:
    """Resume accounting: fold prior sessions' spend for ``run_id`` into a fresh
    ``RunStats`` so the status file's tokens/cost/requests/retries stay
    RUN-level (they would otherwise restart at zero and silently understate
    true spend right after every ``--resume``).

    Records of ALL statuses count — failed/partial attempts cost money too.
    Same parsing tolerance as ``completed_record_ids``: skip blank/corrupt lines.
    """
    p = Path(responses_path)
    if not p.is_file():
        return
    with p.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("run_id") != run_id:
                continue
            usage = rec.get("usage_total") or {}
            for key, wire in RunStats._USAGE_KEYS:
                val = usage.get(wire)
                if val is not None:       # never fabricate 0 for an absent count
                    stats.tokens[key] += int(val)
            transcript = rec.get("transcript") or []
            cost = rec.get("cost_usd_total")
            if cost is None:              # odd/old record: fall back to per-turn costs
                turn_costs = [t.get("cost_usd") for t in transcript
                              if isinstance(t, dict) and t.get("cost_usd") is not None]
                cost = sum(turn_costs) if turn_costs else None
            if cost is not None:
                stats.cost_usd += cost
            stats.add_retries(int(rec.get("retries") or 0))
            stats.requests_done += len(transcript)   # one 200 per recorded turn


class JsonlAppender:
    """Append-only writer. Each append opens/writes/flushes/fsyncs so a crash
    never leaves a half-written line, and an async lock serializes writers."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        async with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())


class StatusWriter:
    """Ephemeral, rebuildable live-progress file for the control panel.

    schema_version 2 keeps every v1 field name and adds run lifecycle, model
    identity, request/retry/token/cost accounting and recent items (fed by the
    shared ``RunStats``). Readers MUST tolerate missing v2 fields: old v1
    status files (no ``schema_version``) still exist on disk.
    """

    def __init__(self, status_dir: str, run_id: str, total: int, *,
                 stats: Optional[RunStats] = None, model=None, concurrency: int = 0):
        self.dir = Path(status_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{run_id}.json"
        self.run_id = run_id
        self.total = total
        self.stats = stats
        self.model = model
        self.concurrency = concurrency
        self._lock = asyncio.Lock()
        self.recent_errors: deque = deque(maxlen=10)

    def note_error(self, item_id: str, kind: str, message: str) -> None:
        self.recent_errors.append({"item_id": item_id, "kind": kind, "message": message[:200]})
        # The single error_counts increment point: the runner calls note_error
        # exactly once per error event (each retry sleep, each final item error,
        # each write failure), so counting here cannot double count.
        if self.stats is not None:
            self.stats.note_error(kind)

    async def write(self, *, completed: int, failed: int, skipped: int,
                    in_flight: int, started_at: str, updated_at: str,
                    throughput_per_min: float, eta_seconds, governor_delay: float,
                    run_status: str = "running", finished_at: Optional[str] = None,
                    abort_reason: Optional[str] = None) -> None:
        st = self.stats if self.stats is not None else RunStats()
        model_block = None
        if self.model is not None:
            model_block = {
                "logical_name": getattr(self.model, "logical_name", None),
                "provider": getattr(self.model, "provider", None),
                "api_model_id": getattr(self.model, "api_model_id", None),
            }
        payload = {
            "schema_version": 2,
            "run_id": self.run_id,
            "run_status": run_status,
            "model": model_block,
            "concurrency": self.concurrency,
            "total": self.total,
            "completed": completed,
            "failed": failed,
            "skipped_existing": skipped,
            "in_flight": in_flight,
            "remaining": max(0, self.total - completed - failed - skipped),
            "requests_done": st.requests_done,
            "retries_total": st.retries_total,
            "throughput_per_min": round(throughput_per_min, 2),
            "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
            "governor_delay_s": round(governor_delay, 2),
            "tokens": dict(st.tokens),
            "cost_usd": round(st.cost_usd, 6),
            "error_counts": dict(st.error_counts),
            "started_at": started_at,
            "updated_at": updated_at,
            "finished_at": finished_at,
            "abort_reason": abort_reason,
            "recent_errors": list(self.recent_errors),
            "recent_items": list(st.recent_items),
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        async with self._lock:
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(self.path)        # atomic on POSIX
