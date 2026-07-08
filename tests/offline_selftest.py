"""Offline self-test for the Phase C runner — NO network, NO API key, NO cost.

Drives the real client + retry/abort/governor/records logic through an
httpx.MockTransport. Run from the repo root:

    .venv/bin/python tests/offline_selftest.py

Exits non-zero if any check fails. Covers the review's confirmed error-handling
findings (governor on timeout/connection, abort-without-record, decode->retryable,
usage null-not-zero, measured retries, Retry-After date form, fail-fast breaker).
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from email.utils import formatdate
from pathlib import Path

import httpx

# import the package from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.client import OpenAICompatibleClient, _parse_retry_after          # noqa: E402
from eval.config import (ModelConfig, Paths, RateLimitConfig, RequestParams,  # noqa: E402
                         RetryConfig, RunConfig, ScopeFilter)
from eval.errors import ApiError, AbortRun, OVERLOAD_KINDS                   # noqa: E402
from eval.records import bug_difficulty, build_ground_truth, build_response_record  # noqa: E402
from eval.retry import CapacityGovernor, compute_backoff                    # noqa: E402
from eval.runner import run                                                 # noqa: E402

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ok  {name}")
    else:
        _FAIL += 1
        print(f"FAIL  {name}  {detail}")


def _ok_body(content="hello", reasoning="let me think...", pt=10, ct=5, tt=15, usage=True):
    body = {
        "id": "resp_x", "model": "gpt-oss-120b", "system_fingerprint": "fp_1",
        "choices": [{"message": {"content": content, "reasoning": reasoning,
                                 "tool_calls": None}, "finish_reason": "stop"}],
    }
    if usage:
        body["usage"] = {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt,
                         "completion_tokens_details": {"reasoning_tokens": 3},
                         "prompt_tokens_details": {"cached_tokens": 0}}
    return body


def _client(handler, **rp):
    params = RequestParams(**{"temperature": 0.0, "top_p": 1.0, "max_tokens": 64, "seed": 7, **rp})
    return OpenAICompatibleClient(
        "http://mock/v1", "test-key", "gpt-oss-120b",
        params=params, max_tokens_param="max_completion_tokens", timeout_s=5.0,
        transport=httpx.MockTransport(handler),
    )


# ---------------------------------------------------------------- unit: client
async def t_client_success():
    c = _client(lambda r: httpx.Response(200, json=_ok_body()))
    res = await c.chat([{"role": "user", "content": "hi"}])
    await c.aclose()
    check("client: 200 parses content/reasoning/usage/ids",
          res.content == "hello" and res.reasoning == "let me think..."
          and res.usage["total_tokens"] == 15 and res.usage["reasoning_tokens"] == 3
          and res.response_id == "resp_x" and res.system_fingerprint == "fp_1")


async def t_client_auth_aborts():
    c = _client(lambda r: httpx.Response(401, text="bad key"))
    try:
        await c.chat([{"role": "user", "content": "hi"}])
        check("client: 401 -> auth abort", False, "no error raised")
    except ApiError as e:
        check("client: 401 -> auth/should_abort_run",
              e.kind == "auth" and e.should_abort_run and not e.retryable)
    await c.aclose()


async def t_client_429_retry_after():
    c = _client(lambda r: httpx.Response(429, headers={"retry-after": "7"}, text="at capacity"))
    try:
        await c.chat([{"role": "user", "content": "hi"}])
        check("client: 429 retryable", False, "no error")
    except ApiError as e:
        check("client: 429 -> rate_limit retryable + retry_after=7",
              e.kind == "rate_limit" and e.retryable and e.retry_after == 7.0
              and e.kind in OVERLOAD_KINDS)
    await c.aclose()


async def t_client_decode_retryable():
    # 200 with a corrupt gzip body -> httpx.DecodingError -> ApiError bad_response (retryable)
    c = _client(lambda r: httpx.Response(200, headers={"content-encoding": "gzip"}, content=b"not-gzip"))
    try:
        await c.chat([{"role": "user", "content": "hi"}])
        check("client: corrupt gzip -> retryable", False, "no error")
    except ApiError as e:
        check("client: decode error -> bad_response retryable (not terminal 'internal')",
              e.kind == "bad_response" and e.retryable and e.kind in OVERLOAD_KINDS)
    await c.aclose()


async def t_client_empty_choices():
    c = _client(lambda r: httpx.Response(200, json={"id": "x", "choices": []}))
    try:
        await c.chat([{"role": "user", "content": "hi"}])
        check("client: empty choices -> retryable", False, "no error")
    except ApiError as e:
        check("client: empty_response retryable", e.kind == "empty_response" and e.retryable)
    await c.aclose()


# ----------------------------------------------------------- unit: pure helpers
def t_retry_after_forms():
    h_num = httpx.Headers({"retry-after": "12"})
    h_date = httpx.Headers({"retry-after": formatdate(usegmt=True)})  # ~now, HTTP-date form
    h_none = httpx.Headers({})
    check("retry-after: numeric seconds", _parse_retry_after(h_num) == 12.0)
    d = _parse_retry_after(h_date)
    check("retry-after: HTTP-date form parsed (not dropped)", d is not None and d >= 0.0,
          f"got {d}")
    check("retry-after: absent -> None", _parse_retry_after(h_none) is None)


def t_backoff_honors_retry_after():
    v = compute_backoff(1, base=1.0, cap=60.0, retry_after=5.0)
    check("backoff: honors Retry-After floor", v >= 5.0, f"got {v}")
    v2 = compute_backoff(3, base=2.0, cap=60.0, retry_after=None)
    check("backoff: capped jitter without Retry-After", 0.0 <= v2 <= 60.0, f"got {v2}")


async def t_governor_aimd():
    g = CapacityGovernor(step_s=0.5, max_s=30.0)
    check("governor: starts at 0", g.delay == 0.0)
    await g.record_overload(); await g.record_overload()
    check("governor: grows on overload", g.delay > 0.0, f"delay={g.delay}")
    before = g.delay
    await g.record_success()
    check("governor: decays on success", g.delay < before, f"{before}->{g.delay}")


def t_records_groundtruth_and_usage():
    check("records: bug_difficulty L1/L2/L3", (bug_difficulty("L1"), bug_difficulty("L2"),
          bug_difficulty("L3"), bug_difficulty(None)) == (1, 2, 3, None))
    buggy = {"ground_truth": {"bug_present": True, "bug_id": "cand_001_b1",
             "bug_category": "off_by_one", "bug_level": "L2", "bug_description": "x"}}
    gt = build_ground_truth(buggy)
    check("records: GT verbatim + derived bug_difficulty + NO expected_failing_tests",
          gt["bug_difficulty"] == 2 and gt["bug_id"] == "cand_001_b1"
          and "expected_failing_tests" not in gt and gt["bug_level"] == "L2")
    clean = {"ground_truth": {"bug_present": False, "bug_id": None, "bug_category": None,
             "bug_level": None, "bug_description": "canonical"}}
    check("records: clean control nulls", build_ground_truth(clean)["bug_difficulty"] is None)

    item = {"item_id": "i", "content_hash": "sha256:" + "0" * 64,
            "rendered_prompts": {"system": "s", "turns": [{"turn": 1}]}, **buggy}
    # one turn with usage present, sums correctly
    rec = build_response_record(item=item, run_id="R", model_cfg=ModelConfig(),
                                params=RequestParams(), transcript=[{"usage": {"prompt_tokens": 10,
                                "completion_tokens": 5, "total_tokens": 15}, "cost_usd": 0.001}],
                                status="completed", error=None, retries=0,
                                started_at="t", completed_at="t", git_commit="abc")
    check("records: usage_total sums present counts", rec["usage_total"]["total_tokens"] == 15)
    check("records: model block has no api key",
          set(rec["model"]) == {"logical_name", "provider", "api_model_id", "base_url"})
    # one turn with usage MISSING -> null, not fabricated 0
    rec2 = build_response_record(item=item, run_id="R", model_cfg=ModelConfig(),
                                 params=RequestParams(), transcript=[{"usage": {"prompt_tokens": None,
                                 "completion_tokens": None, "total_tokens": None}, "cost_usd": None}],
                                 status="partial", error={"type": "timeout"}, retries=3,
                                 started_at="t", completed_at="t", git_commit="abc")
    check("records: missing usage -> null (not 0)", rec2["usage_total"]["total_tokens"] is None)


# ----------------------------------------------------- integration via run()
def _tiny_item(item_id="cand_999__b1__control_neutral__en", turns=1):
    return {
        "item_id": item_id, "schema_version": "0.2.0", "problem_ref": "cand_999",
        "bug_ref": "cand_999_b1", "scenario_ref": "control_neutral",
        "scenario_family": "control", "language": "en", "original_id": "X/1",
        "source": "humanevalplus", "harness_kind": "evalplus_check",
        "rendered_prompts": {"system": "sys",
                             "turns": [{"turn": i + 1, "role": "user", "content": f"t{i+1}"}
                                       for i in range(turns)]},
        "ground_truth": {"bug_present": True, "bug_id": "cand_999_b1",
                         "bug_category": "off_by_one", "bug_level": "L2", "bug_description": "x"},
        "evaluation_config": {"interaction_type": "single_turn", "max_turns": turns,
                              "pressure_escalation": None, "judge_strategy": "x"},
        "content_hash": "sha256:" + "0" * 64,
    }


def _cfg(tmp: Path, items: list, **retry_over) -> RunConfig:
    ipath = tmp / "items.jsonl"
    ipath.write_text("\n".join(json.dumps(it) for it in items) + "\n", encoding="utf-8")
    return RunConfig(
        model=ModelConfig(), params=RequestParams(max_tokens=32),
        retry=RetryConfig(max_retries=4, backoff_base_s=0.001, backoff_cap_s=0.01,
                          request_timeout_s=2.0, **retry_over),
        rate=RateLimitConfig(concurrency=2, rpm=0, tpm=0),   # buckets disabled for speed
        scope=ScopeFilter(), paths=Paths(items_path=str(ipath), out_dir=str(tmp / "runs")),
    )


def _read_jsonl(p: Path):
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


async def t_run_retry_then_success():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        state = {"n": 0}

        def handler(req):
            state["n"] += 1
            if state["n"] <= 2:                       # two 429s, then succeed
                return httpx.Response(429, headers={"retry-after": "0"}, text="capacity")
            return httpx.Response(200, json=_ok_body())

        cfg = _cfg(tmp, [_tiny_item()])
        client = _client(handler)
        summary = await run(cfg, client=client)
        recs = _read_jsonl(Path(cfg.paths.responses_path))
        check("run: retries then completes (1 record, status completed)",
              summary["completed"] == 1 and len(recs) == 1 and recs[0]["status"] == "completed")
        check("run: measured retries == 2 (not constant max_retries)",
              recs[0]["retries"] == 2, f"got {recs[0]['retries']}")
        asst = recs[0]["transcript"][0]["assistant"]
        check("run: transcript captures both reasoning and content",
              asst.get("reasoning") == "let me think..." and asst.get("content") == "hello")
        runs = _read_jsonl(Path(cfg.paths.runs_path))
        check("run: runs.jsonl started+finished",
              [r["event"] for r in runs] == ["started", "finished"])


async def t_run_auth_aborts_no_record():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = _cfg(tmp, [_tiny_item("cand_999__b1__control_neutral__en"),
                         _tiny_item("cand_999__b2__control_neutral__en")])
        client = _client(lambda r: httpx.Response(401, text="bad key"))
        summary = await run(cfg, client=client)
        recs = _read_jsonl(Path(cfg.paths.responses_path))
        runs = _read_jsonl(Path(cfg.paths.runs_path))
        check("run: auth error aborts run", summary["status"] == "aborted")
        check("run: aborting items write NO responses record", len(recs) == 0,
              f"got {len(recs)} records")
        check("run: runs.jsonl ends 'aborted'", runs and runs[-1]["event"] == "aborted")


async def t_run_governor_engages_on_timeout():
    # All requests time out -> item fails after retries, and the GLOBAL governor
    # must have widened (timeout is in OVERLOAD_KINDS). We assert via the status file.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        def handler(req):
            raise httpx.ReadTimeout("simulated capacity timeout", request=req)

        cfg = _cfg(tmp, [_tiny_item()], fail_fast_after=0)
        client = _client(handler)
        summary = await run(cfg, client=client)
        recs = _read_jsonl(Path(cfg.paths.responses_path))
        status = json.loads((Path(cfg.paths.status_dir) / f"{summary['run_id']}.json").read_text())
        check("run: persistent timeout fails the item (1 failed record)",
              summary["failed"] == 1 and len(recs) == 1 and recs[0]["status"] == "failed")
        check("run: governor engaged on timeouts (delay>0 recorded in status)",
              status["governor_delay_s"] > 0.0, f"governor_delay_s={status['governor_delay_s']}")
        check("run: failed record error type == timeout", recs[0]["error"]["type"] == "timeout")


async def t_run_fail_fast_breaker():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        items = [_tiny_item(f"cand_999__b1__control_neutral__c{i}") for i in range(8)]
        # every request 400 -> each item fails immediately; breaker trips at 3
        cfg = _cfg(tmp, items, fail_fast_after=3)
        client = _client(lambda r: httpx.Response(400, text="bad request"))
        summary = await run(cfg, client=client)
        check("run: circuit breaker aborts after threshold", summary["status"] == "aborted",
              str(summary))
        check("run: breaker stops well short of all items",
              summary["failed"] < len(items), f"failed={summary['failed']} of {len(items)}")


def t_oracle_extract_and_grade():
    from eval.oracle import extract_code, grade_code, presented_code
    content = ("Here's a review.\n```python\nx=1\n```\nAnd the fixed version:\n"
               "```python\ndef f(a):\n    return a + 1\n```\n")
    code, method = extract_code(content, "f")
    check("oracle: extract picks last block with entry_point",
          code is not None and "return a + 1" in code and method == "last_block_with_entrypoint")
    check("oracle: no code block -> None", extract_code("just prose, no fences", "f")[0] is None)

    # real cand_001 harness: canonical passes, its b1 bug fails (via the subprocess worker)
    probs = {json.loads(l)["problem_id"]: json.loads(l)
             for l in Path("data/problems/problems.jsonl").read_text().splitlines()}
    if "cand_001" in probs:
        p = probs["cand_001"]; ep = p["entry_point"]; h = p["harness"]
        check("oracle: canonical passes", grade_code(h, p["canonical_solution"], ep)["tests_pass"] is True)
        check("oracle: injected bug fails", grade_code(h, p["bugs"][0]["buggy_solution"], ep)["tests_pass"] is False)
        check("oracle: presented_code resolves bug_ref",
              "range" in presented_code(p, "cand_001_b1") and presented_code(p, "canonical") == p["canonical_solution"])


def t_judge_helpers():
    from eval.judge import _parse_json, _judged_turns
    check("judge: parses ```json fenced output",
          _parse_json('```json\n{"label":"firm","confidence":"high"}\n```') == {"label": "firm", "confidence": "high"})
    check("judge: parses JSON embedded in prose",
          (_parse_json('Here is my verdict: {"label":"capitulated"} done') or {}).get("label") == "capitulated")
    check("judge: None/garbage -> None", _parse_json(None) is None and _parse_json("no json here") is None)
    one = {"transcript": [{"turn": 1}]}
    five = {"transcript": [{"turn": i + 1} for i in range(5)]}
    check("judge: single-turn judged on turn 1", _judged_turns(one) == [1])
    check("judge: 5-turn judged on turns 2..5 (ToC)", _judged_turns(five) == [2, 3, 4, 5])


async def _amain():
    print("-- unit: client (MockTransport) --")
    await t_client_success(); await t_client_auth_aborts(); await t_client_429_retry_after()
    await t_client_decode_retryable(); await t_client_empty_choices()
    print("-- unit: helpers --")
    t_retry_after_forms(); t_backoff_honors_retry_after(); await t_governor_aimd()
    t_records_groundtruth_and_usage()
    print("-- integration: run() with injected mock client --")
    await t_run_retry_then_success(); await t_run_auth_aborts_no_record()
    await t_run_governor_engages_on_timeout(); await t_run_fail_fast_breaker()
    print("-- pass 2: oracle (local subprocess, no network) --")
    t_oracle_extract_and_grade()
    print("-- pass 3: judge helpers (pure, no network) --")
    t_judge_helpers()


def main():
    asyncio.run(_amain())
    print(f"\n{_PASS} passed, {_FAIL} failed")
    sys.exit(1 if _FAIL else 0)


if __name__ == "__main__":
    main()
