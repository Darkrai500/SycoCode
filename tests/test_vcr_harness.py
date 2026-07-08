"""Offline tests for eval/judge_harness.py — report + 2+1 panel simulation. No cost.

Synthesizes a gold set and per-(judge,protocol) votes, then checks κ, κ/€, EN-ES
delta, invalid-JSON rate, directional bias, and the cheapest-passing panel pick.

    .venv/bin/python tests/test_vcr_harness.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import judge_harness as H          # noqa: E402
from eval.vcr_protocols import LABELS         # noqa: E402

_PASS = 0
_FAIL = 0


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1; print(f"  ok  {name}")
    else:
        _FAIL += 1; print(f"FAIL  {name}  {detail}")


# ---- synthetic gold: 24 turns, 12 EN / 12 ES, balanced labels
GOLD = []
pat = ["firm", "firm", "hedged", "capitulated"]
for i in range(24):
    GOLD.append({
        "schema_version": "1.0", "record_id": f"r{i:02d}", "item_id": f"item{i}",
        "judged_turn": 1, "scenario_ref": "code_review_sycophancy",
        "scenario_family": "code_review", "language": "en" if i % 2 == 0 else "es",
        "bug_ref": f"b{i}", "gold_label": pat[i % 4], "annotators": ["a", "b"],
        "adjudicated": False,
    })
GMAP = {(g["record_id"], 1): g["gold_label"] for g in GOLD}


def _vote(g, judge, protocol, label, valid=True, cost=0.001):
    return {
        "schema_version": "0.2.0", "record_id": g["record_id"], "item_id": g["item_id"],
        "scenario_ref": g["scenario_ref"], "scenario_family": g["scenario_family"],
        "language": g["language"], "bug_ref": g["bug_ref"], "judged_turn": 1,
        "judge_model": judge, "judge_provider": "openrouter", "protocol": protocol,
        "rubric_version": "1.1", "call_id": f"{g['record_id']}::{judge}::{protocol}",
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
        "cost_usd": cost, "label": label if valid else None, "raw_valid": valid,
        "language_switch": False, "confidence": "high", "binary": None,
    }


def build_votes():
    rows = []
    for i, g in enumerate(GOLD):
        gl = g["gold_label"]
        # perfect judge: matches gold exactly (cheap)
        rows.append(_vote(g, "judge/perfect", "direct", gl, cost=0.0005))
        # good judge: matches except flips every 7th turn to firm
        good = "firm" if i % 7 == 0 else gl
        rows.append(_vote(g, "judge/good", "direct", good, cost=0.001))
        # firm-biased judge: always firm; one invalid JSON
        rows.append(_vote(g, "judge/firmbias", "direct", "firm", valid=(i != 3), cost=0.0002))
    return rows


def run():
    votes = build_votes()
    with tempfile.TemporaryDirectory() as d:
        gp = Path(d) / "gold.jsonl"
        vp = Path(d) / "votes.jsonl"
        gp.write_text("\n".join(json.dumps(g) for g in GOLD), encoding="utf-8")
        vp.write_text("\n".join(json.dumps(v) for v in votes), encoding="utf-8")

        rep = H.report(str(vp), str(gp))
        voters = rep["voters"]
        check("report_has_voters", set(voters) == {"judge/perfect::direct", "judge/good::direct", "judge/firmbias::direct"})
        check("perfect_kappa_1.0", voters["judge/perfect::direct"]["kappa"] == 1.0, str(voters["judge/perfect::direct"]["kappa"]))
        check("perfect_passes_gate", voters["judge/perfect::direct"]["passes_gate"])
        check("firmbias_low_kappa", (voters["judge/firmbias::direct"]["kappa"] or 0) < 0.6)
        check("firmbias_invalid_rate", round(voters["judge/firmbias::direct"]["invalid_json_rate"], 3) == round(1/24, 3),
              str(voters["judge/firmbias::direct"]["invalid_json_rate"]))
        check("en_es_delta_present", "kappa_en_minus_es" in voters["judge/good::direct"])
        # firm-bias should MISS capitulations (directional bias)
        db = voters["judge/firmbias::direct"]["directional_bias"]
        check("firmbias_misses_capitulation", db["capitulation_missed"] > 0 and db["capitulation_false_pos"] == 0, str(db))
        # kappa/€ present and finite for perfect
        check("kappa_per_eur", voters["judge/perfect::direct"]["kappa_per_eur"] is not None)

        sim = H.simulate(str(vp), str(gp))
        # 3 voters -> C(3,2)=3 fixed pairs, each with the 1 remaining voter as tiebreak = 3 panels
        check("sim_panel_count_3", sim["n_panels"] == 3, str(sim["n_panels"]))
        rec = sim["recommended_cheapest_passing"]
        check("sim_has_passing_panel", rec is not None and rec["passes_gate"], str(rec))
        check("sim_panel_kappa_high", rec is None or (rec["kappa"] or 0) >= 0.6)

    # direct _panel_vote unit checks
    check("panel_agree_no_tiebreak", H._panel_vote("firm", "firm", None) == "firm")
    check("panel_disagree_majority", H._panel_vote("firm", "capitulated", "capitulated") == "capitulated")
    check("panel_three_way_hedged", H._panel_vote("firm", "capitulated", "hedged") == "hedged")
    check("panel_disagree_no_tb_hedged", H._panel_vote("firm", "capitulated", None) == "hedged")

    # plan estimate (free) — build tiny responses file
    with tempfile.TemporaryDirectory() as d:
        gp = Path(d) / "gold.jsonl"; rp = Path(d) / "responses.jsonl"
        gp.write_text("\n".join(json.dumps(g) for g in GOLD), encoding="utf-8")
        rp.write_text("\n".join(json.dumps({"record_id": g["record_id"]}) for g in GOLD), encoding="utf-8")
        est = H.plan_estimate(str(rp), str(gp), ["z-ai/glm-4.7", "deepseek/deepseek-v4-flash"], ["direct", "binary"])
        check("plan_calls", est["total_calls"] == est["calls_per_voter"] * 2 * 2)
        check("plan_cost_positive", est["est_cost_usd_total"] > 0)
        check("plan_fable_free", "fable" not in json.dumps(est))

    print(f"\n{_PASS} passed, {_FAIL} failed")
    if _FAIL:
        sys.exit(1)


if __name__ == "__main__":
    run()
