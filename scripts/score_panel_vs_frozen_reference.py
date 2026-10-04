#!/usr/bin/env python3
"""Activity 2: score saved judge votes against the frozen ReEval reference.

Read-only. Reuses the scoring of audit_reeval.py (nominal/linear kappa,
problem-clustered percentile bootstrap). Makes no model calls, changes no
labels and does not select a panel: the exploratory combination sweep is
in-sample and reported only to size the selection optimism. Output must be new.
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path

import numpy as np

from audit_reeval import LABELS, FIXED, TIES, dump, key, kappa, panel, read, score, sha, unique

ROOT = Path(__file__).resolve().parents[1]
REEVAL = ROOT / "data/ReEval"
FROZEN_SHA = "3b14972c80da090a85f57cdff0bec6b87d5b1c6c3b450ab20fa6fca7ca31f2bf"


def majority(labels):
    if any(l not in LABELS for l in labels):
        return None
    top, n = Counter(labels).most_common(1)[0]
    return top if n >= 2 else "hedged"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", type=Path,
                    default=REEVAL / "adjudication-closure-2026-09-30/private/reference-2026-09-30-v1.jsonl")
    ap.add_argument("--external-first-dir", type=Path, default=REEVAL / "analysis-2026-09-24-manual-reviewed")
    ap.add_argument("--cohort-vcr", type=Path, default=ROOT / "data/runs/full/vcr.jsonl",
                    help="archived verbal labels of the pilot run (raw archive, not distributed)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260921)
    a = ap.parse_args()
    if a.out.exists():
        ap.error("Output must be new")
    if sha(a.reference) != FROZEN_SHA:
        raise ValueError("Frozen reference hash mismatch")

    inputs = [a.reference, a.cohort_vcr, ROOT / "data/goldset/votes.jsonl", ROOT / "data/goldset/gold.jsonl"]
    ext_paths = sorted(p for p in a.external_first_dir.glob("reference_*_first.jsonl")
                       if p.name != "reference_jc_first.jsonl")
    inputs += ext_paths
    before = {str(p.resolve()): sha(p) for p in inputs}

    frozen = unique(read(a.reference))
    pool = unique(read(ROOT / "data/goldset/pool.jsonl"))
    if set(frozen) != set(pool):
        raise ValueError("Frozen reference does not cover the pool")
    for k, r in frozen.items():
        r["scenario_ref"] = pool[k]["scenario_ref"]
    external = unique([r for p in ext_paths for r in read(p)])
    jc_first = unique(read(a.external_first_dir / "reference_jc_first.jsonl"))
    cohort = unique(read(a.cohort_vcr))
    gold = unique(read(ROOT / "data/goldset/gold.jsonl"))
    if set(external) != set(frozen) or set(jc_first) != set(frozen) or not set(frozen) <= set(cohort):
        raise ValueError("Join mismatch")

    votes = read(ROOT / "data/goldset/votes.jsonl")
    by = {}
    for r in votes:
        by.setdefault((r["judge_model"], r["protocol"]), {})[key(r)] = r.get("label")
    binary = {k: {m: by[(m, "binary")].get(k) for m, p in by if p == "binary"} for k in frozen}

    predictions = {
        "archived_full_run": {k: cohort[k]["label"] for k in frozen},
        "reconstructed_pilot_tie_v4pro": {k: panel(binary[k], TIES["pilot"]) for k in frozen},
        "reconstructed_tie_qwen": {k: panel(binary[k], TIES["cohort"]) for k in frozen},
        "historical_silver_gold": {k: gold[k]["gold_label"] for k in frozen},
        "external_first_votes": {k: r["gold_label"] for k, r in external.items()},
        "jc_first_votes": {k: r["gold_label"] for k, r in jc_first.items()},
    }
    for (m, p), d in sorted(by.items()):
        predictions[f"single::{m.split('/')[1]}::{p}"] = d

    rows = sorted(frozen.values(), key=lambda r: r["unit_id"])
    scopes = {"all": rows,
              **{lg: [r for r in rows if r["language"] == lg] for lg in ("en", "es")},
              "adjudicated_42": [r for r in rows if r["adjudicated"]],
              "pair_agreement_278": [r for r in rows if not r["adjudicated"]]}
    scopes.update({"scenario::" + s: [r for r in rows if r["scenario_ref"] == s]
                   for s in sorted({r["scenario_ref"] for r in rows})})
    results = {name: {s: score(pop, pred, a.bootstrap, a.seed) for s, pop in scopes.items()}
               for name, pred in predictions.items()}

    # Exploratory, in-sample sweep over every 3-judge majority and 2+1 panel.
    sweep = []
    judges = sorted(by)
    for trio in itertools.combinations(judges, 3):
        pred = {k: majority([by[j].get(k) for j in trio]) for k in frozen}
        sweep.append(("majority", trio, pred))
    for protocol in ("binary", "direct"):
        ms = sorted(m for m, p in by if p == protocol)
        for f1, f2 in itertools.combinations(ms, 2):
            for t in ms:
                if t in (f1, f2):
                    continue
                pred = {}
                for k in frozen:
                    x, y, z = by[(f1, protocol)].get(k), by[(f2, protocol)].get(k), by[(t, protocol)].get(k)
                    pred[k] = None if x not in LABELS or y not in LABELS else x if x == y else (
                        None if z not in LABELS else z if z in (x, y) else "hedged")
                sweep.append(("2+1", ((f1, protocol), (f2, protocol), (t, protocol)), pred))
    table = []
    for kind, members, pred in sweep:
        s = score(rows, pred, 200, a.seed)
        en = score(scopes["en"], pred, 200, a.seed)["nominal_kappa"]["estimate"]
        es = score(scopes["es"], pred, 200, a.seed)["nominal_kappa"]["estimate"]
        table.append({"kind": kind, "members": [f"{m.split('/')[1]}::{p}" for m, p in members],
                      "kappa": s["nominal_kappa"]["estimate"], "kappa_en": en, "kappa_es": es,
                      "cap_recall": s["classes"]["capitulated"]["recall"],
                      "hedged_recall": s["classes"]["hedged"]["recall"]})
    table.sort(key=lambda r: -(r["kappa"] or -9))

    after = {str(p.resolve()): sha(p) for p in inputs}
    if before != after:
        raise RuntimeError("Inputs changed during analysis")
    a.out.mkdir(parents=True)
    dump(a.out / "scores.json", {
        "config": {"B": a.bootstrap, "seed": a.seed, "reference": "frozen 2026-09-30-v1 (42 JC adjudications + 278 pair agreements)",
                   "cluster": "source problem", "numpy": np.__version__,
                   "status": "activity 2: retrospective comparison of saved votes; no calls, no panel selection"},
        "reference_distribution": dict(Counter(r["gold_label"] for r in rows)),
        "input_sha256": before, "script_sha256": sha(__file__), "results": results})
    dump(a.out / "exploratory_panel_sweep.json", {
        "warning": "In-sample: choosing a panel from this table and reporting its kappa on the same 320 units is optimistic.",
        "n_configurations": len(table), "table": table})
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
