#!/usr/bin/env python3
"""Exploratory checks on the held-out reference (ReEval-2) that are NOT in its analysis plan.

The planned analysis is ``score_reeval2.py``. This script adds the splits reported as
exploratory in the article's Supplementary Material (Section S11): they were chosen
after the results were seen, and no claim rests on them.

* the panel on the turns where the two annotators agree, and on the adjudicated turns;
* bounds over the two annotators' labels on the adjudicated turns;
* turns decided by the tie-breaker against turns where the two fixed judges agreed;
* the analysis without the one sampled turn that is a provider error message;
* the panel against each annotator's first labels;
* counts: where human capitulations fall in the panel's labels, single-turn turns.

Reads only the released files; makes no network calls; writes only ``--out``.

    python scripts/reeval2_exploratory.py --out data/reeval2/reeval2_exploratory.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also under python -I
import score_reeval2 as s2  # noqa: E402
from score_human_reference import read  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "reeval2"
PROVIDER_ERROR_UNIT = "r2u0020"  # deviation D4 in docs/methodology/reeval2_protocol_record.md


def brief(units, ref, pred):
    out = {}
    for name, weighted in (("sample", False), ("design_weighted", True)):
        s = s2.weighted_score(units, ref, pred, weighted)
        cap = s["classes"]["capitulated"]
        out[name] = {"n": s["n"], "agreement": s["agreement"], "kappa": s["kappa"], "ci95": s["ci95"],
                     "capitulated_recall": cap["recall"], "capitulated_recall_ci95": cap["recall_ci95"],
                     "capitulated_precision": cap["precision"]}
    out["panel_equals_reference"] = sum(ref[u["unit_id"]] == pred[u["unit_id"]] for u in units)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", type=Path, default=DATA / "sample_key.jsonl")
    ap.add_argument("--labels", type=Path, default=DATA / "export" / "sycocode-jsonl.jsonl")
    ap.add_argument("--adjudication", type=Path, default=DATA / "export" / "sycocode-reeval-adjudications.jsonl")
    ap.add_argument("--annotators", default="a1,a2", help="Two accounts, comma-separated: A1,A2.")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    a1, a2 = args.annotators.split(",")
    units = read(args.key)
    ref, first, current, _, missing, unexpected = s2.build_reference(
        units, read(args.labels), read(args.adjudication), a1, a2)
    if missing or unexpected:
        raise SystemExit(f"Incomplete or inconsistent labels: missing={missing[:10]} unexpected={unexpected[:10]}")
    panel = {u["unit_id"]: u["panel_label"] for u in units}

    def uid(u):
        return u["unit_id"]

    agreed = [u for u in units if current[a1][uid(u)] == current[a2][uid(u)]]
    queued = [u for u in units if current[a1][uid(u)] != current[a2][uid(u)]]
    # Bounds: on each adjudicated turn take the annotator label equal to the panel's where
    # there is one (A1's otherwise), or one different from it (A1's when both differ).
    closest, furthest = dict(ref), dict(ref)
    for u in queued:
        options = [current[a1][uid(u)], current[a2][uid(u)]]
        closest[uid(u)] = panel[uid(u)] if panel[uid(u)] in options else options[0]
        furthest[uid(u)] = [o for o in options if o != panel[uid(u)]][0]
    single = [u for u in units if s2.scenario_type(u) == "single_turn"]

    result = {
        "note": "Exploratory: not in the analysis plan of docs/methodology/reeval2_protocol.md.",
        "first_label_disagreements": sum(first[a1][uid(u)] != first[a2][uid(u)] for u in units),
        "hand_in_label_disagreements": len(queued),
        "converged_before_hand_in": sum(first[a1][uid(u)] != first[a2][uid(u)] for u in agreed),
        "diverged_before_hand_in": sum(first[a1][uid(u)] == first[a2][uid(u)] for u in queued),
        "adjudicated_label_equals_panel": sum(ref[uid(u)] == panel[uid(u)] for u in queued),
        "capitulations_both_annotators": {
            "n": sum(ref[uid(u)] == "capitulated" for u in agreed),
            "panel_found": sum(ref[uid(u)] == panel[uid(u)] == "capitulated" for u in agreed)},
        "capitulations_from_adjudication": {
            "n": sum(ref[uid(u)] == "capitulated" for u in queued),
            "panel_found": sum(ref[uid(u)] == panel[uid(u)] == "capitulated" for u in queued)},
        "missed_capitulations_by_panel_label": dict(collections.Counter(
            panel[uid(u)] for u in units if ref[uid(u)] == "capitulated" and panel[uid(u)] != "capitulated")),
        "reference_by_panel_label": {
            lab: dict(collections.Counter(ref[uid(u)] for u in units if panel[uid(u)] == lab))
            for lab in ("firm", "hedged", "capitulated")},
        "panel_firm_design_weight": round(sum(u["design_weight"] for u in units if panel[uid(u)] == "firm"), 6),
        "total_design_weight": round(sum(u["design_weight"] for u in units), 6),
        "single_turn": {
            "n": len(single),
            "reference": dict(collections.Counter(ref[uid(u)] for u in single)),
            "panel": dict(collections.Counter(panel[uid(u)] for u in single)),
            "a2_capitulated_at_hand_in": sum(current[a2][uid(u)] == "capitulated" for u in single)},
        "tiebreak_turns": sum(bool(u["tiebreak_used"]) for u in units),
        "checks": {
            "agreed_turns_only": brief(agreed, ref, panel),
            "adjudicated_turns_only": brief(queued, ref, panel),
            "fixed_judges_agreed": brief([u for u in units if not u["tiebreak_used"]], ref, panel),
            "tiebreak_decided": brief([u for u in units if u["tiebreak_used"]], ref, panel),
            "without_provider_error_turn": brief([u for u in units if uid(u) != PROVIDER_ERROR_UNIT], ref, panel),
            "panel_vs_a1_first_labels": brief(units, first[a1], panel),
            "panel_vs_a2_first_labels": brief(units, first[a2], panel),
            "bound_annotator_label_equal_to_panel": brief(units, closest, panel),
            "bound_annotator_label_different_from_panel": brief(units, furthest, panel),
        },
    }
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    for name, score in result["checks"].items():
        s = score["sample"]
        ci = "[{:.2f}, {:.2f}]".format(*s["ci95"]) if s["ci95"] else ""
        print(f"  {name:44s} n={s['n']:3d}  panel=ref {score['panel_equals_reference']:3d}  kappa {s['kappa']:.3f} {ci}")


if __name__ == "__main__":
    main()
