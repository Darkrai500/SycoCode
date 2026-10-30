#!/usr/bin/env python3
"""Offline tests for score_reeval2.py (standalone script; exits non-zero on failure).

1. With unit weights, the scorer reproduces the released agreement of the archived
   pilot panel with the human reference (score_human_reference.py).
2. Design weights act as frequency weights: duplicating a unit is equivalent to
   doubling its weight.
3. Reference construction: agreements stand, disagreements take the adjudicated
   label, and a missing adjudication is reported, not filled in.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_human_reference as shr  # noqa: E402
import score_reeval2 as s2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FAILURES = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        FAILURES.append(name)


def test_matches_released_scorer():
    rows = shr.read(ROOT / "data/reeval/human_reference_v1.jsonl")
    ref = {shr.key(r): r["reference_label"] for r in rows}
    pred = {shr.key(r): r["panel_label_archived"] for r in rows}
    old = shr.score(rows, ref, pred, 2000, 1)
    units = [{"unit_id": r["unit_id"], "problem_ref": shr.problem(r), "language": r["language"],
              "design_weight": 7.0} for r in rows]
    new = s2.weighted_score(units, {r["unit_id"]: r["reference_label"] for r in rows},
                            {r["unit_id"]: r["panel_label_archived"] for r in rows}, weighted=False, bootstrap=2000, seed=1)
    check("unweighted kappa equals released scorer (0.624)",
          abs(new["kappa"] - old["kappa"]) < 1e-12 and round(new["kappa"], 3) == 0.624)
    check("unweighted confusion equals released scorer", new["confusion_rows_reference"] == old["confusion_rows_reference"])
    check("same bootstrap interval with the same seed", new["ci95"] == old["ci95"])
    weighted = s2.weighted_score(units, {r["unit_id"]: r["reference_label"] for r in rows},
                                 {r["unit_id"]: r["panel_label_archived"] for r in rows}, weighted=True, bootstrap=200)
    check("constant weights leave kappa unchanged", abs(weighted["kappa"] - old["kappa"]) < 1e-12)


def test_weights_are_frequency_weights():
    base = [("p1", "firm", "firm", 1.0), ("p1", "hedged", "firm", 1.0), ("p2", "capitulated", "capitulated", 1.0),
            ("p2", "firm", "hedged", 1.0), ("p3", "hedged", "hedged", 1.0), ("p3", "firm", "firm", 1.0)]
    dup = base + [base[1]]
    wtd = [b if i != 1 else (*b[:3], 2.0) for i, b in enumerate(base)]

    def run(spec):
        units = [{"unit_id": f"u{i}", "problem_ref": p, "language": "en", "design_weight": w} for i, (p, _, _, w) in enumerate(spec)]
        ref = {f"u{i}": r for i, (_, r, _, _) in enumerate(spec)}
        pred = {f"u{i}": q for i, (_, _, q, _) in enumerate(spec)}
        return s2.weighted_score(units, ref, pred, weighted=True, bootstrap=50)["kappa"]
    check("doubling a weight equals duplicating the unit", abs(run(dup) - run(wtd)) < 1e-12)


def test_reference_construction():
    units = [{"unit_id": u} for u in ("a", "b", "c")]
    labels = [{"unit_id": "a", "annotator": "x", "label": "firm", "first_label": "hedged"},
              {"unit_id": "a", "annotator": "y", "label": "firm", "first_label": "firm"},
              {"unit_id": "b", "annotator": "x", "label": "firm", "first_label": "firm"},
              {"unit_id": "b", "annotator": "y", "label": "hedged", "first_label": "hedged"},
              {"unit_id": "c", "annotator": "x", "label": "capitulated", "first_label": "capitulated"},
              {"unit_id": "c", "annotator": "y", "label": "firm", "first_label": "firm"}]
    adjudication = [{"unit_id": "b", "label": "hedged"}]
    ref, first, current, source, missing, unexpected = s2.build_reference(units, labels, adjudication, "x", "y")
    check("agreed unit keeps the common current label", ref.get("a") == "firm" and first["x"]["a"] == "hedged")
    check("disagreement takes the adjudicated label", ref.get("b") == "hedged" and source.get("adjudicated_to_A2") == 1)
    check("missing adjudication is reported", missing == ["c"] and "c" not in ref)
    _, _, _, _, _, unexpected = s2.build_reference(units, labels, adjudication + [{"unit_id": "a", "label": "firm"}], "x", "y")
    check("adjudication of an agreed unit is flagged", unexpected == ["a"])
    exported = [{"unit_id": "b", "decision": {"label": "firm"}}, {"unit_id": "c", "decision": {"label": "hedged"}}]
    ref, _, _, source, missing, _ = s2.build_reference(units, labels, exported, "x", "y")
    check("application decision export is read", ref == {"a": "firm", "b": "firm", "c": "hedged"} and not missing
          and source.get("adjudicated_to_A1") == 1 and source.get("adjudicated_to_third_label") == 1)


if __name__ == "__main__":
    test_matches_released_scorer()
    test_weights_are_frequency_weights()
    test_reference_construction()
    sys.exit(1 if FAILURES else 0)
