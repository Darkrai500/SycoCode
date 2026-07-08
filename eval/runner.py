"""The Pass-1 generation loop.

For each in-scope item it walks the FULL declared turn ladder (1, 2, or 5 turns),
sending accumulated history + the next user turn and capturing the assistant
reply. It never stops early on a perceived flip (judgment is Pass 2/3). One
atomic responses.jsonl record is written per item only when the item terminates.
"""
from __future__ import annotations

import asyncio
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from .client import OpenAICompatibleClient
from .errors import OVERLOAD_KINDS, AbortRun, ApiError
from .items import dataset_hash, scoped_items
from .pricing import cost_usd
from .progress import ProgressReporter, RunStats
from .records import build_response_record, build_run_event, record_id
from .retry import CapacityGovernor, TokenBucket, compute_backoff
from .store import JsonlAppender, StatusWriter, completed_record_ids, seed_run_stats

# Heartbeat: refresh status/progress liveness even when no item completes (a
# sustained 429/timeout window can park every worker in backoff for 10-18 min).
_HEARTBEAT_INTERVAL_S = 20.0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mint_run_id(logical_name: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"{ts}__{logical_name}__{uuid.uuid4().hex[:6]}"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _estimate_tokens(messages: List[dict], max_tokens: int) -> float:
    chars = sum(len(m.get("content") or "") for m in messages)
    return chars / 4.0 + max_tokens          # rough; used only for TPM pacing


def _turn_coverage(items: List[dict]) -> dict:
    cov: dict = {}
    for it in items:
        n = len((it.get("rendered_prompts", {}) or {}).get("turns", []) or [])
        cov[n] = cov.get(n, 0) + 1
    return {f"{k}_turn": v for k, v in sorted(cov.items())}


async def run(cfg, *, client=None) -> dict:
    # `client` is an injection seam for offline tests; None = build a real one.
    items = scoped_items(cfg.paths.items_path, cfg.scope)
    if not items:
        raise SystemExit("No items match the scope filter.")

    run_id = cfg.resume_run_id or _mint_run_id(cfg.model.logical_name)
    skip = completed_record_ids(cfg.paths.responses_path, run_id) if cfg.resume_run_id else set()
    pending = [it for it in items if record_id(run_id, it["item_id"]) not in skip]

    if cfg.dry_run:
        return {
            "dry_run": True,
            "run_id": run_id,
            "items_path": cfg.paths.items_path,
            "scope_item_count": len(items),
            "already_completed": len(skip),
            "to_run": len(pending),
            "turn_coverage": _turn_coverage(pending),
            "languages": sorted({it.get("language") for it in pending}),
            "scenarios": sorted({it.get("scenario_ref") for it in pending}),
            "estimated_api_requests": sum(
                len((it.get("rendered_prompts", {}) or {}).get("turns", []) or []) for it in pending
            ),
        }

    git_commit = _git_commit()
    ds_hash = dataset_hash(cfg.paths.items_path)
    api_key = cfg.resolve_api_key() if client is None else None

    responses = JsonlAppender(cfg.paths.responses_path)
    runs = JsonlAppender(cfg.paths.runs_path)
    stats = RunStats()                            # shared by StatusWriter AND the reporter
    if cfg.resume_run_id:
        # Run-level spend: fold prior sessions' tokens/cost/requests/retries for
        # this run_id into the fresh stats — the StatusWriter overwrites the same
        # status/<run_id>.json, so session-only numbers would understate spend.
        seed_run_stats(cfg.paths.responses_path, run_id, stats)
    status = StatusWriter(cfg.paths.status_dir, run_id, total=len(items),
                          stats=stats, model=cfg.model, concurrency=cfg.rate.concurrency)

    rpm_bucket = TokenBucket(cfg.rate.rpm / 60.0) if cfg.rate.rpm > 0 else None
    tpm_bucket = (TokenBucket(cfg.rate.tpm / 60.0, capacity=cfg.rate.tpm)
                  if cfg.rate.tpm > 0 else None)
    governor = CapacityGovernor()
    sem = asyncio.Semaphore(cfg.rate.concurrency)

    client = client or OpenAICompatibleClient(
        cfg.model.base_url, api_key, cfg.model.api_model_id,
        params=cfg.params, max_tokens_param=cfg.model.max_tokens_param,
        timeout_s=cfg.retry.request_timeout_s,
    )

    counts = {"completed": 0, "failed": 0, "skipped_existing": len(skip)}
    started_at = _utcnow_iso()
    started_monotonic = time.monotonic()
    in_flight = {"n": 0}
    abort = {"set": False, "reason": None}
    fail_streak = {"n": 0}

    # Live references (counts/in_flight/governor) let the reporter read current
    # values at render time; stats mutations flow through its event hooks.
    reporter = ProgressReporter(
        mode=getattr(cfg, "progress_mode", "auto"), run_id=run_id, model=cfg.model,
        total=len(items), skipped_existing=len(skip), to_run=len(pending),
        concurrency=cfg.rate.concurrency, stats=stats, counts=counts,
        in_flight=in_flight, governor=governor, status_path=str(status.path),
    )

    async def refresh_status(*, run_status: str = "running",
                             finished_at: Optional[str] = None,
                             abort_reason: Optional[str] = None) -> None:
        done = counts["completed"] + counts["failed"]
        elapsed_min = max(1e-9, (time.monotonic() - started_monotonic) / 60.0)
        thr = done / elapsed_min
        eta = ((len(pending) - done) / thr * 60.0) if (thr > 0 and done > 0) else None
        try:
            await status.write(
                completed=counts["completed"], failed=counts["failed"],
                skipped=counts["skipped_existing"], in_flight=in_flight["n"],
                started_at=started_at, updated_at=_utcnow_iso(),
                throughput_per_min=thr, eta_seconds=eta, governor_delay=governor.delay,
                run_status=run_status, finished_at=finished_at, abort_reason=abort_reason,
            )
        except OSError:
            pass                                  # status file is disposable; never crash on it

    def trip_breaker_if_needed() -> None:
        limit = cfg.retry.fail_fast_after
        if limit and limit > 0 and fail_streak["n"] >= limit and not abort["set"]:
            abort["set"] = True
            abort["reason"] = (f"circuit breaker: {fail_streak['n']} consecutive item "
                               f"failures — endpoint likely unavailable")

    async def call_with_retry(messages: List[dict], item_id: str):
        """One assistant turn, with pacing + automatic retry. Returns (result, retries).
        Raises AbortRun on a terminal credential/endpoint error; raises the final
        ApiError (with .attempts set) when retries are exhausted."""
        attempt = 0
        while True:
            await governor.wait()
            if rpm_bucket is not None:
                await rpm_bucket.acquire(1.0)
            if tpm_bucket is not None:
                await tpm_bucket.acquire(_estimate_tokens(messages, cfg.params.max_tokens))
            try:
                result = await client.chat(messages)
                await governor.record_success()
                return result, attempt
            except ApiError as e:
                if e.should_abort_run:
                    abort["set"] = True
                    abort["reason"] = abort["reason"] or str(e)
                    raise AbortRun(str(e), attempts=attempt)
                if e.kind in OVERLOAD_KINDS:
                    await governor.record_overload()
                if (not e.retryable) or (attempt >= cfg.retry.max_retries):
                    e.attempts = attempt          # surface the true measured count
                    raise
                status.note_error(item_id, e.kind, str(e))
                reporter.on_retry(e.kind)
                delay = compute_backoff(attempt + 1, cfg.retry.backoff_base_s,
                                        cfg.retry.backoff_cap_s, e.retry_after)
                await asyncio.sleep(delay)
                attempt += 1

    async def run_item(item: dict) -> None:
        if abort["set"]:
            return                                # never started -> leave no record
        item_id = item["item_id"]
        rp = item.get("rendered_prompts", {}) or {}
        turns = sorted(rp.get("turns", []) or [], key=lambda t: t.get("turn", 0))

        messages: List[dict] = []
        system_prompt = rp.get("system")
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})

        transcript: List[dict] = []
        item_started = _utcnow_iso()
        item_t0 = time.monotonic()
        total_retries = 0
        status_str = "completed"
        error_obj: Optional[dict] = None

        for turn in turns:
            if abort["set"]:
                return                            # bail mid-ladder: leave no record (redo on resume)
            user_msg = {"role": "user", "content": turn.get("content", "")}
            messages.append(user_msg)
            requested_at = _utcnow_iso()
            t0 = time.monotonic()
            try:
                result, attempts = await call_with_retry(messages, item_id)
            except AbortRun:
                raise                             # propagate; aborting item writes NO record
            except ApiError as e:
                total_retries += getattr(e, "attempts", 0)
                stats.add_retries(getattr(e, "attempts", 0))
                error_obj = {"type": e.kind, "message": str(e), "last_turn": turn.get("turn")}
                status_str = "partial" if transcript else "failed"
                status.note_error(item_id, e.kind, str(e))
                reporter.on_error(item_id, e.kind)
                break
            except Exception as e:                # noqa: BLE001 - never let one item kill the run
                error_obj = {"type": "internal", "message": repr(e)[:300], "last_turn": turn.get("turn")}
                status_str = "partial" if transcript else "failed"
                status.note_error(item_id, "internal", repr(e))
                reporter.on_error(item_id, "internal")
                break

            latency_ms = int((time.monotonic() - t0) * 1000)
            total_retries += attempts
            stats.add_retries(attempts)
            c = cost_usd(cfg.model.provider, cfg.model.api_model_id,
                         result.usage.get("prompt_tokens"),
                         result.usage.get("completion_tokens"))
            reporter.on_turn_done(result.usage, c)
            transcript.append({
                "turn": turn.get("turn"),
                "user_messages": [user_msg],
                "assistant": {
                    "content": result.content,
                    "reasoning": result.reasoning,
                    "finish_reason": result.finish_reason,
                    "tool_calls": result.tool_calls,
                },
                "usage": result.usage,
                "provider_meta": {
                    "response_id": result.response_id,
                    "system_fingerprint": result.system_fingerprint,
                    "model_returned": result.model_returned,
                },
                "timing": {"requested_at": requested_at, "latency_ms": latency_ms},
                "cost_usd": c,
            })
            messages.append({"role": "assistant", "content": result.content or ""})

        item_cost: Optional[float] = None        # None when no turn had a known cost
        for t in transcript:
            if t.get("cost_usd") is not None:
                item_cost = (item_cost or 0.0) + t["cost_usd"]
        item_latency_ms = int((time.monotonic() - item_t0) * 1000)

        record = build_response_record(
            item=item, run_id=run_id, model_cfg=cfg.model, params=cfg.params,
            transcript=transcript, status=status_str, error=error_obj,
            retries=total_retries, started_at=item_started,
            completed_at=_utcnow_iso(), git_commit=git_commit,
        )
        try:
            await responses.append(record)
        except Exception as e:                    # disk-write failure fails ONE item, not the run
            status.note_error(item_id, "write_error", repr(e))
            reporter.on_error(item_id, "write_error")
            counts["failed"] += 1
            fail_streak["n"] += 1
            trip_breaker_if_needed()
            reporter.on_item_done(item_id, "failed", item_latency_ms, item_cost, len(transcript))
            await refresh_status()
            return

        if status_str == "completed":
            counts["completed"] += 1
            fail_streak["n"] = 0
        else:
            counts["failed"] += 1
            fail_streak["n"] += 1
            trip_breaker_if_needed()
        reporter.on_item_done(item_id, status_str, item_latency_ms, item_cost, len(transcript))
        await refresh_status()

    async def worker(item: dict) -> None:
        async with sem:
            in_flight["n"] += 1
            try:
                await run_item(item)
            finally:
                in_flight["n"] -= 1

    await runs.append(build_run_event(
        run_id=run_id, event="started", model_cfg=cfg.model, params=cfg.params,
        items_path=cfg.paths.items_path, items_hash=ds_hash, scope=cfg.scope,
        scope_count=len(items), counts=dict(counts), status="running",
        concurrency=cfg.rate.concurrency, started_at=started_at,
        updated_at=started_at, finished_at=None, git_commit=git_commit,
    ))
    await refresh_status()

    async def heartbeat() -> None:
        # Liveness during backoff storms: refresh_status() otherwise runs only on
        # item completion, so updated_at goes stale while every worker sleeps in
        # backoff and the panel reports a healthy money-spending run as stalled.
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
            await refresh_status()                # swallows OSError internally
            reporter.heartbeat()                  # never raises

    # Created inside the try below so a startup failure (e.g. Live.start() on a
    # degraded terminal) still reaches the finally: heartbeat cancelled, terminal
    # restored, terminal status written, client closed.
    heartbeat_task: Optional[asyncio.Task] = None
    tasks: List[asyncio.Task] = []
    final_status = "completed"
    try:
        heartbeat_task = asyncio.create_task(heartbeat())
        reporter.start()
        tasks = [asyncio.create_task(worker(it)) for it in pending]
        await asyncio.gather(*tasks)
        if abort["set"]:
            final_status = "aborted"
    except (AbortRun, KeyboardInterrupt, asyncio.CancelledError) as e:
        final_status = "aborted"
        abort["set"] = True
        abort["reason"] = abort["reason"] or (str(e) or "interrupted")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)   # let cancellations settle
    except Exception as e:                # noqa: BLE001 - unexpected crash: finalize as
        final_status = "aborted"          # aborted (never "finished"), then re-raise
        abort["set"] = True
        abort["reason"] = abort["reason"] or f"internal failure: {e!r}"[:300]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)  # let the cancel settle
        finished_at = _utcnow_iso()
        # Stop the Live display FIRST so a Ctrl-C never leaves the terminal broken
        # and the final JSON summary on stdout is not interleaved with redraws.
        reporter.finish(final_status, abort["reason"])
        try:
            await runs.append(build_run_event(
                run_id=run_id, event="aborted" if final_status == "aborted" else "finished",
                model_cfg=cfg.model, params=cfg.params, items_path=cfg.paths.items_path,
                items_hash=ds_hash, scope=cfg.scope, scope_count=len(items),
                counts=dict(counts), status=final_status, concurrency=cfg.rate.concurrency,
                started_at=started_at, updated_at=finished_at, finished_at=finished_at,
                git_commit=git_commit,
            ))
        except OSError:
            pass
        try:
            # Independent of the runs.jsonl append above: the terminal status
            # write must always execute or run_status stays "running" forever.
            await refresh_status(
                run_status="finished" if final_status == "completed" else "aborted",
                finished_at=finished_at, abort_reason=abort["reason"],
            )
        except OSError:
            pass
        await client.aclose()

    return {
        "dry_run": False,
        "run_id": run_id,
        "status": final_status,
        "abort_reason": abort["reason"],
        "scope_item_count": len(items),
        "skipped_existing": counts["skipped_existing"],
        "completed": counts["completed"],
        "failed": counts["failed"],
        "responses_path": cfg.paths.responses_path,
        "runs_path": cfg.paths.runs_path,
        "status_path": str(status.path),
    }
