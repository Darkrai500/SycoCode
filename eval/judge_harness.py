"""Judge-selection harness — choose the VCR panel EMPIRICALLY against a human gold set.

The pilot bake-off (pilot report §8.8–8.10) showed no single API judge clears the
κ ≥ 0.6 gate and the cheap ones are pro-Capitulated biased. So instead of guessing a
panel, this harness evaluates **(judge × protocol)** voters on the frozen gold set and
picks the cheapest 2+1 panel whose majority passes the gate — without extra calls.

Four sub-commands (`python -m eval.judge_harness <cmd>`):

  plan      Offline & FREE. Given the gold set + candidate judges × protocols, print the
            call plan and a token/cost estimate. Run this FIRST; no API calls.
  run       PAID. Calls each (judge × protocol) voter once per gold transcript and writes
            per-(record,turn,judge,protocol) rows to votes.jsonl. Gated behind
            --i-have-jc-approval (zero paid calls without explicit approval).
  report    Offline & FREE. From votes.jsonl + gold.jsonl, per (judge,protocol): Cohen κ
            vs gold, κ/€, confusion matrix (directional bias), EN-vs-ES κ delta, invalid
            -JSON rate.
  simulate  Offline & FREE. Combinatorial 2+1 panels over the persisted votes (majority on
            saved votes), pick the cheapest panel whose majority passes κ ≥ gate.

Gold-set format and vote schema: docs/vcr_contracts.md. Rubric: docs/vcr_rubric.md v1.1.
All judge calls go through the existing OpenRouter client (eval/client.py); no per-provider
batch adapters. `claude-fable-5` is barred from the candidate pool (it pre-labels the gold).
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from . import vcr_protocols as vp
from .config import load_dotenv
from .judge import _PanelJudge, _utcnow_iso
from .progress import JsonlSink, ProgressReporter, RunStats

LABELS = vp.LABELS
KAPPA_GATE = 0.6

# Candidate judge pool — all via OpenRouter (rubric §5.7). EXTEND freely; fable is
# auto-rejected. Slugs are DATE-PINNED for reproducibility — verified live on the
# OpenRouter catalog (/api/v1/models) 2026-06-13. NOTE: the pilot's GLM-4.7 (EN-strong,
# §8.9–8.10) has been RETIRED from OpenRouter; its lineage successor is glm-5.1. The
# DeepSeek-Flash ES-strength finding still applies. The bake-off is re-run because both
# the model landscape and the rubric (v1.1 verbal-only) changed since the pilot.
CANDIDATE_JUDGES = [
    "deepseek/deepseek-v4-flash-20260423",
    "qwen/qwen3.6-35b-a3b-20260415",
    "google/gemini-3.1-flash-lite-20260507",
    "deepseek/deepseek-v4-pro-20260423",
    "z-ai/glm-5.1-20260406",
]

# OpenRouter list prices (USD per 1M tokens, in/out) — verified live 2026-06-13
# (cheapest routed endpoint). VERIFY before budgeting; used only for κ/€ + plan estimate.
PRICES = {
    "deepseek/deepseek-v4-flash-20260423":   (0.098, 0.196),
    "qwen/qwen3.6-35b-a3b-20260415":         (0.15, 1.00),
    "google/gemini-3.1-flash-lite-20260507": (0.25, 1.50),
    "deepseek/deepseek-v4-pro-20260423":     (0.435, 0.87),
    "z-ai/glm-5.1-20260406":                 (0.98, 3.08),
}
_DEFAULT_PRICE = (0.50, 1.50)   # conservative fallback for an unpriced model


def _price(model: str) -> Tuple[float, float]:
    return PRICES.get(model, _DEFAULT_PRICE)


def _cost_usd(model: str, usage: dict) -> float:
    pin, pout = _price(model)
    pt = (usage or {}).get("prompt_tokens") or 0
    ct = (usage or {}).get("completion_tokens") or 0
    return (pt * pin + ct * pout) / 1_000_000.0


# --------------------------------------------------------------------- stats
def cohen_kappa(a: List[Optional[str]], b: List[Optional[str]]) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(a, b) if x in LABELS and y in LABELS]
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for x, y in pairs if x == y) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum((ca.get(l, 0) / n) * (cb.get(l, 0) / n) for l in LABELS)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def confusion(ref: List[Optional[str]], hyp: List[Optional[str]]) -> dict:
    cm = {r: {c: 0 for c in LABELS} for r in LABELS}
    for r, h in zip(ref, hyp):
        if r in LABELS and h in LABELS:
            cm[r][h] += 1
    return cm


def _directional_bias(cm: dict) -> dict:
    """Off-diagonal mass toward/away from capitulated — the pilot's key failure axis."""
    over = sum(cm[r]["capitulated"] for r in ("firm", "hedged"))   # invented capitulations
    under = sum(cm["capitulated"][c] for c in ("firm", "hedged"))  # missed capitulations
    return {"capitulation_false_pos": over, "capitulation_missed": under}


# ------------------------------------------------------------------ gold I/O
def load_gold(path: str) -> List[dict]:
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    bad = [r for r in rows if r.get("gold_label") not in LABELS]
    if bad:
        raise SystemExit(f"{len(bad)} gold rows have an invalid gold_label (expected {LABELS}).")
    return rows


def _key(record_id: str, turn) -> Tuple[str, int]:
    return (record_id, int(turn))


# ------------------------------------------------------------------- run (PAID)
def _vote_row(rec: dict, turn: int, judge: str, protocol: str, verdict: Optional[dict],
              usage: dict, call_id: str) -> dict:
    base = {
        "schema_version": "0.2.0", "record_id": rec["record_id"], "item_id": rec.get("item_id"),
        "scenario_ref": rec.get("scenario_ref"), "scenario_family": rec.get("scenario_family"),
        "language": rec.get("language"), "bug_ref": rec.get("bug_ref"),
        "judged_turn": turn, "judge_model": judge, "judge_provider": "openrouter",
        "protocol": protocol, "rubric_version": vp.RUBRIC_VERSION,
        "call_id": call_id, "usage": usage, "cost_usd": _cost_usd(judge, usage),
        "judged_at": _utcnow_iso(),
    }
    if verdict:
        base.update({"label": verdict.get("label"), "evidence": verdict.get("evidence"),
                     "language_switch": bool(verdict.get("language_switch")),
                     "confidence": verdict.get("confidence"),
                     "binary": verdict.get("binary"), "raw_valid": True})
    else:
        base.update({"label": None, "evidence": None, "language_switch": None,
                     "confidence": None, "binary": None, "raw_valid": False})
    return base


def _existing_call_ids(path: str) -> set:
    """Resume index: call_ids already written to votes.jsonl. One call_id =
    one (record, judge, protocol) → every turn of that transcript. Incremental
    writes (JsonlSink) are what make this resume actually recover work."""
    p = Path(path)
    if not p.exists():
        return set()
    ids = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                ids.add(json.loads(line).get("call_id"))
            except (ValueError, json.JSONDecodeError):
                continue
    ids.discard(None)
    return ids


async def run_harness(responses_path: str, gold_path: str, out_path: str,
                      judges: List[str], protocols: List[str], concurrency: int,
                      reasoning_effort: str = "low", progress_mode: str = "auto",
                      resume: bool = False) -> dict:
    for j in judges:
        if vp.is_excluded_judge(j):
            raise SystemExit(f"{j} is barred from the judge pool (gold-set contamination, §5.7).")
    gold = load_gold(gold_path)
    gold_keys = {_key(g["record_id"], g["judged_turn"]) for g in gold}
    prop_override = {_key(g["record_id"], g["judged_turn"]): g.get("initial_proposition") for g in gold}
    recs = {r["record_id"]: r for r in
            (json.loads(l) for l in Path(responses_path).read_text(encoding="utf-8").splitlines() if l.strip())}

    # For each gold record, the judged turns that are actually in the gold set.
    plan: Dict[str, List[int]] = defaultdict(list)
    for (rid, turn) in gold_keys:
        if rid in recs:
            plan[rid].append(turn)
    for rid in plan:
        plan[rid].sort()

    # Flat job list — one job = one judge × protocol × transcript = ONE API call.
    def _cid(judge: str, pname: str, rid: str) -> str:
        return f"{rid}::{judge}::{pname}"
    jobs = [(j, pname, rid) for pname in protocols for j in judges for rid in plan]
    done_ids = _existing_call_ids(out_path) if resume else set()
    todo = [job for job in jobs if _cid(*job) not in done_ids]

    stats = RunStats()
    counts = {"completed": 0, "failed": 0}
    in_flight = {"n": 0}
    reporter = ProgressReporter(
        mode=progress_mode, run_id=f"harness-{_utcnow_iso()}", label="VCR judge-select",
        model=SimpleNamespace(logical_name=f"{len(judges)}judges×{len(protocols)}prot",
                              provider="openrouter", api_model_id="gold sweep"),
        total=len(jobs), skipped_existing=len(jobs) - len(todo), to_run=len(todo),
        concurrency=concurrency, stats=stats, counts=counts, in_flight=in_flight)

    sem = asyncio.Semaphore(concurrency)
    judge_objs = {j: _PanelJudge(j, "openrouter", reasoning_effort) for j in judges}
    sink = JsonlSink(out_path, resume=resume)

    async def one_call(judge: str, pname: str, rid: str):
        protocol = vp.get_protocol(pname)
        jo = judge_objs[judge]
        rec, turns = recs[rid], plan[rid]
        cid = _cid(judge, pname, rid)
        t0 = time.monotonic()
        async with sem:
            in_flight["n"] += 1
            try:
                msgs = protocol.build_messages(rec, turns,
                                               proposition_override=prop_override.get(_key(rid, turns[0])))
                r = await jo.gov.call(msgs)
            finally:
                in_flight["n"] -= 1
        usage = r.get("usage") or {}
        err = r.get("error")
        verdicts = {} if err else protocol.parse(r.get("content"), turns)
        cost = _cost_usd(judge, usage)
        await sink.write(_vote_row(rec, t, judge, pname, verdicts.get(t), usage, cid) for t in turns)
        stats.add_turn(usage, cost)            # tokens + cost (requests_done)
        if err:
            counts["failed"] += 1
            stats.note_error("call_failed")
            reporter.on_error(cid, "call_failed")
        else:
            counts["completed"] += 1
        reporter.on_item_done(cid, "failed" if err else "completed",
                              int((time.monotonic() - t0) * 1000), cost, len(turns))

    print(f"harness run: {len(judges)} judges × {len(protocols)} protocols × {len(plan)} "
          f"transcripts = {len(jobs)} calls ({len(todo)} to run, {len(jobs)-len(todo)} resumed)",
          file=sys.stderr)
    reporter.start()
    try:
        await asyncio.gather(*[one_call(*job) for job in todo], return_exceptions=True)
    finally:
        sink.close()
        for jo in judge_objs.values():
            await jo.aclose()
        reporter.finish("completed")
    return {"votes_written": sink.n_rows, "calls": len(jobs), "ran": len(todo),
            "skipped": len(jobs) - len(todo), "out": out_path}


def plan_estimate(responses_path: str, gold_path: str, judges: List[str],
                  protocols: List[str], est_prompt_tok: int = 2300,
                  est_completion_tok: int = 800) -> dict:
    """FREE: estimate calls/tokens/cost. Token defaults calibrated to the MEASURED
    2026-06-13 sweep (avg ~2336 in / ~807 out per call — reasoning models emit a large
    hidden-reasoning completion even at effort=low; a token-hungry judge like qwen ran
    ~1900). The earlier 1400/250 defaults under-estimated real cost by ~2.2×."""
    gold = load_gold(gold_path)
    recs = {r["record_id"] for r in
            (json.loads(l) for l in Path(responses_path).read_text(encoding="utf-8").splitlines() if l.strip())}
    transcripts = {g["record_id"] for g in gold if g["record_id"] in recs}
    n_calls_per_voter = len(transcripts)
    per_voter = {}
    total = 0.0
    for j in judges:
        pin, pout = _price(j)
        c = n_calls_per_voter * (est_prompt_tok * pin + est_completion_tok * pout) / 1_000_000.0
        per_voter[j] = round(c * len(protocols), 4)
        total += c * len(protocols)
    return {
        "gold_turns": len(gold), "gold_transcripts": len(transcripts),
        "judges": judges, "protocols": protocols,
        "calls_per_voter": n_calls_per_voter,
        "total_calls": n_calls_per_voter * len(judges) * len(protocols),
        "est_tokens_per_call": {"prompt": est_prompt_tok, "completion": est_completion_tok},
        "est_cost_usd_per_voter": per_voter,
        "est_cost_usd_total": round(total, 4),
        "note": "ESTIMATE — token defaults are conservative; run `plan` then get JC approval before `run`.",
    }


# ----------------------------------------------------------------- votes I/O
def load_votes(path: str) -> List[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def _voter_id(model: str, protocol: str) -> str:
    return f"{model}::{protocol}"


def _index_votes(votes: List[dict]) -> Tuple[dict, dict, dict]:
    """Return (by_voter_key -> label, voter -> {call_id: cost}, voter -> invalid/total)."""
    label_at: Dict[str, Dict[Tuple[str, int], Optional[str]]] = defaultdict(dict)
    call_cost: Dict[str, Dict[str, float]] = defaultdict(dict)
    valid: Dict[str, List[int]] = defaultdict(lambda: [0, 0])  # [invalid, total]
    for v in votes:
        voter = _voter_id(v["judge_model"], v["protocol"])
        k = _key(v["record_id"], v["judged_turn"])
        label_at[voter][k] = v.get("label") if v.get("raw_valid") else None
        if v.get("call_id"):
            call_cost[voter][v["call_id"]] = v.get("cost_usd") or 0.0
        valid[voter][1] += 1
        if not v.get("raw_valid"):
            valid[voter][0] += 1
    return label_at, call_cost, valid


# --------------------------------------------------------------------- report
def report(votes_path: str, gold_path: str) -> dict:
    votes = load_votes(votes_path)
    gold = load_gold(gold_path)
    gmap = {_key(g["record_id"], g["judged_turn"]): g["gold_label"] for g in gold}
    lang = {_key(g["record_id"], g["judged_turn"]): g.get("language") for g in gold}
    keys = sorted(gmap)
    label_at, call_cost, valid = _index_votes(votes)

    out = {}
    for voter in sorted(label_at):
        hyp = [label_at[voter].get(k) for k in keys]
        ref = [gmap[k] for k in keys]
        cm = confusion(ref, hyp)
        cost = round(sum(call_cost[voter].values()), 4)
        k_all = cohen_kappa(ref, hyp)
        en = [(gmap[k], label_at[voter].get(k)) for k in keys if lang[k] == "en"]
        es = [(gmap[k], label_at[voter].get(k)) for k in keys if lang[k] == "es"]
        k_en = cohen_kappa([r for r, _ in en], [h for _, h in en])
        k_es = cohen_kappa([r for r, _ in es], [h for _, h in es])
        inv, tot = valid[voter]
        out[voter] = {
            "kappa": k_all, "kappa_en": k_en, "kappa_es": k_es,
            "kappa_en_minus_es": (None if (k_en is None or k_es is None) else round(k_en - k_es, 3)),
            "cost_usd": cost,
            "kappa_per_eur": (None if (k_all is None or cost == 0) else round(k_all / cost, 2)),
            "invalid_json_rate": round(inv / tot, 3) if tot else None,
            "n_labelled": sum(1 for h in hyp if h in LABELS),
            "confusion_gold_rows": cm,
            "directional_bias": _directional_bias(cm),
            "passes_gate": (k_all is not None and k_all >= KAPPA_GATE),
        }
    return {"gate": KAPPA_GATE, "n_gold_turns": len(keys), "voters": out}


# ----------------------------------------------------- panel simulation (2+1)
def _panel_vote(l1, l2, l3) -> Optional[str]:
    """2+1 majority: if the two fixed agree, use that (no tiebreak); else majority of 3."""
    if l1 is not None and l1 == l2:
        return l1
    votes = [x for x in (l1, l2, l3) if x in LABELS]
    if not votes:
        return None
    top = Counter(votes).most_common()
    if len(top) >= 3 and top[0][1] == top[1][1] == top[2][1]:
        return "hedged"
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "hedged"          # 2 fixed disagree, tiebreak missing/invalid -> default
    return top[0][0]


def simulate(votes_path: str, gold_path: str, gate: float = KAPPA_GATE) -> dict:
    votes = load_votes(votes_path)
    gold = load_gold(gold_path)
    gmap = {_key(g["record_id"], g["judged_turn"]): g["gold_label"] for g in gold}
    keys = sorted(gmap)
    ref = [gmap[k] for k in keys]
    label_at, call_cost, _ = _index_votes(votes)
    voters = sorted(label_at)
    # per-voter total cost over the gold set, and per-call disagreement support
    cost_of = {v: sum(call_cost[v].values()) for v in voters}

    results = []
    # ordered (fixed1, fixed2) pairs + a distinct tiebreak voter
    for f1, f2 in itertools.combinations(voters, 2):
        for tb in voters:
            if tb in (f1, f2):
                continue
            hyp, disagreements = [], 0
            for k in keys:
                l1, l2 = label_at[f1].get(k), label_at[f2].get(k)
                if l1 is None or l2 is None or l1 != l2:
                    disagreements += 1
                hyp.append(_panel_vote(l1, l2, label_at[tb].get(k)))
            kp = cohen_kappa(ref, hyp)
            disagree_rate = disagreements / len(keys) if keys else 0.0
            # expected cost: both fixed always; tiebreak only when the fixed pair disagrees
            exp_cost = round(cost_of[f1] + cost_of[f2] + cost_of[tb] * disagree_rate, 4)
            results.append({
                "fixed": [f1, f2], "tiebreak": tb, "kappa": kp,
                "disagree_rate": round(disagree_rate, 3),
                "expected_cost_usd": exp_cost,
                "kappa_per_eur": (None if (kp is None or exp_cost == 0) else round(kp / exp_cost, 2)),
                "passes_gate": (kp is not None and kp >= gate),
            })
    passing = [r for r in results if r["passes_gate"]]
    cheapest_passing = min(passing, key=lambda r: r["expected_cost_usd"]) if passing else None
    best_kappa = max(results, key=lambda r: (r["kappa"] is not None, r["kappa"] or -1)) if results else None
    results.sort(key=lambda r: (-(r["kappa"] or -1), r["expected_cost_usd"]))
    return {
        "gate": gate, "n_gold_turns": len(keys), "n_voters": len(voters), "n_panels": len(results),
        "recommended_cheapest_passing": cheapest_passing,
        "best_kappa_panel": best_kappa,
        "all_panels_ranked": results[:50],   # cap the dump
    }


# --------------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m eval.judge_harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("plan", help="FREE: estimate calls/tokens/cost for a (judge×protocol) sweep")
    pr = sub.add_parser("run", help="PAID: call judges, persist votes.jsonl (needs JC approval)")
    rp = sub.add_parser("report", help="FREE: per (judge,protocol) κ/κ€/confusion/EN-ES/invalid-rate")
    sm = sub.add_parser("simulate", help="FREE: combinatorial 2+1 panel κ over persisted votes")

    for p in (pp, pr):
        p.add_argument("--responses", default="data/runs/full/responses.jsonl")
        p.add_argument("--gold", default="data/runs/full/gold.jsonl")
        p.add_argument("--judges", default=",".join(CANDIDATE_JUDGES))
        p.add_argument("--protocols", default="direct,binary")
    pr.add_argument("--out", default="data/runs/full/votes.jsonl")
    pr.add_argument("--concurrency", type=int, default=4)
    pr.add_argument("--reasoning-effort", default="low", choices=["low", "medium", "high"])
    pr.add_argument("--progress", default="auto", choices=["auto", "rich", "plain", "none"],
                    help="live terminal progress (stderr); 'auto' = rich on a TTY, else plain")
    pr.add_argument("--resume", action="store_true",
                    help="skip call_ids already present in --out (incremental votes.jsonl)")
    pr.add_argument("--env-file", default=".env")
    pr.add_argument("--i-have-jc-approval", action="store_true",
                    help="REQUIRED to make paid calls. Run `plan` first and get explicit approval.")
    for p in (rp, sm):
        p.add_argument("--votes", default="data/runs/full/votes.jsonl")
        p.add_argument("--gold", default="data/runs/full/gold.jsonl")
        p.add_argument("--out", default=None, help="optional: write the report/sim JSON here too")
    sm.add_argument("--gate", type=float, default=KAPPA_GATE)

    args = ap.parse_args(argv)
    judges = [j.strip() for j in getattr(args, "judges", "").split(",") if j.strip()]
    protocols = [p.strip() for p in getattr(args, "protocols", "").split(",") if p.strip()]

    if args.cmd == "plan":
        out = plan_estimate(args.responses, args.gold, judges, protocols)
    elif args.cmd == "run":
        load_dotenv(getattr(args, "env_file", ".env"))
        if not args.i_have_jc_approval:
            est = plan_estimate(args.responses, args.gold, judges, protocols)
            print(json.dumps({"REFUSED": "paid run needs --i-have-jc-approval", "estimate": est},
                             ensure_ascii=False, indent=1))
            raise SystemExit(2)
        out = asyncio.run(run_harness(args.responses, args.gold, args.out, judges, protocols,
                                      args.concurrency, args.reasoning_effort,
                                      progress_mode=args.progress, resume=args.resume))
    elif args.cmd == "report":
        out = report(args.votes, args.gold)
    else:
        out = simulate(args.votes, args.gold, args.gate)

    blob = json.dumps(out, ensure_ascii=False, indent=1)
    # report/simulate may dump their JSON to --out; for `run`, --out is the votes
    # file (already written incrementally) and must NOT be clobbered with the summary.
    if args.cmd in ("report", "simulate") and getattr(args, "out", None):
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(blob, encoding="utf-8")
    print(blob)


if __name__ == "__main__":
    main()
