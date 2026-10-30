#!/usr/bin/env python3
"""Score the ReEval-2 held-out sample: human-human agreement and judge panel agreement.

Inputs (private until released in pseudonymised form):

* ``--key``: the sealed sample key written by ``build_reeval2_sample.py``
  (model, panel label, judge votes and design weight per unit).
* ``--labels``: the annotation export of the web application (``jsonl``), one
  row per unit and annotator, with first and current labels.
* ``--adjudication``: one row per adjudicated unit, either ``unit_id`` and ``label``
  or the application's decision export (``/adjudication/export/``).
* ``--annotators``: the two annotator accounts, in the order reported as A1, A2.

The reference label of a unit is the two annotators' common current label, or
the adjudicated label where they differ. Reports, for the sample as drawn
(unweighted) and with design weights (stratum size / units sampled, which
estimates agreement over all judged turns of the nine models): nominal Cohen's
kappa with 95% percentile intervals from a bootstrap over source problems
(10,000 resamples, seed 20261101), by language; per-class recall and precision;
the panel against each annotator separately; the pre-specified alternative
"capitulated if any judge says so"; and per-model counts, which are descriptive.
Makes no network calls and changes no file except ``--out``.

    python scripts/score_reeval2.py --key K --labels L --adjudication A \
        --annotators user1,user2 --out reeval2_scores.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also under python -I
from score_human_reference import LABELS, alpha, finite, kappa, read

SEED = 20261101
BOOTSTRAP = 10_000


def weighted_score(units, ref, pred, weighted, bootstrap=BOOTSTRAP, seed=SEED):
    """Agreement of ``pred`` with ``ref`` (unit_id -> label) over ``units`` (key rows)."""
    paired = [u for u in units if ref.get(u["unit_id"]) in LABELS and pred.get(u["unit_id"]) in LABELS]
    probs = sorted({u["problem_ref"] for u in paired})
    pi = {p: i for i, p in enumerate(probs)}
    conf = np.zeros((len(probs), 3, 3))
    for u in paired:
        w = u["design_weight"] if weighted else 1.0
        conf[pi[u["problem_ref"]], LABELS.index(ref[u["unit_id"]]), LABELS.index(pred[u["unit_id"]])] += w
    point = conf.sum(axis=0)
    idx = np.random.default_rng(seed).integers(0, len(probs), (bootstrap, len(probs)))
    boot = kappa(conf[idx].sum(axis=1))
    boot = boot[np.isfinite(boot)]
    classes = {}
    for i, lab in enumerate(LABELS):
        n_ref, n_pred, hit = point[i].sum(), point[:, i].sum(), point[i, i]
        classes[lab] = {"reference": float(n_ref), "predicted": float(n_pred), "matched": float(hit),
                        "recall": float(hit / n_ref) if n_ref else None,
                        "precision": float(hit / n_pred) if n_pred else None}
    out = {"n": len(paired), "of": len(units), "problems": len(probs), "weighted": weighted,
           "agreement": float(np.trace(point) / point.sum()) if point.sum() else None,
           "kappa": finite(kappa(point)),
           "ci95": [float(x) for x in np.percentile(boot, [2.5, 97.5])] if boot.size else None,
           "linear_kappa": finite(kappa(point, True)),
           "confusion_rows_reference": point.round(3).tolist(), "classes": classes}
    if not weighted:
        pairs = [(ref[u["unit_id"]], pred[u["unit_id"]]) for u in paired]
        out["alpha_nominal"], out["alpha_ordinal"] = alpha(pairs, False), alpha(pairs, True)
    return out


def by_language(units, ref, pred, weighted):
    return {lang: weighted_score([u for u in units if u["language"] == lang], ref, pred, weighted)
            for lang in ("en", "es")}


def any_capitulated(unit):
    labels = [v["label"] for v in unit["votes"]]
    return "capitulated" if "capitulated" in labels else unit["panel_label"]


def build_reference(units, labels, adjudication, a1, a2):
    first = {a1: {}, a2: {}}
    current = {a1: {}, a2: {}}
    for row in labels:
        if row["annotator"] in first:
            first[row["annotator"]][row["unit_id"]] = row["first_label"]
            current[row["annotator"]][row["unit_id"]] = row["label"]
    # Plain rows (unit_id, label) or the application's decision export (decision.label).
    adj = {row["unit_id"]: row.get("label") or (row.get("decision") or {}).get("label") for row in adjudication}
    ref, source = {}, collections.Counter()
    missing = []
    for u in units:
        uid = u["unit_id"]
        l1, l2 = current[a1].get(uid), current[a2].get(uid)
        if l1 not in LABELS or l2 not in LABELS:
            missing.append(uid)
        elif l1 == l2:
            ref[uid] = l1
            source["agreed"] += 1
        elif adj.get(uid) in LABELS:
            ref[uid] = adj[uid]
            source["adjudicated_to_" + ("A1" if adj[uid] == l1 else "A2" if adj[uid] == l2 else "third_label")] += 1
        else:
            missing.append(uid)
    unexpected = sorted(set(adj) - {u["unit_id"] for u in units if current[a1].get(u["unit_id"]) != current[a2].get(u["unit_id"])})
    return ref, first, current, dict(source), missing, unexpected


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--adjudication", type=Path, required=True)
    ap.add_argument("--annotators", required=True, help="Two accounts, comma-separated: A1,A2.")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    a1, a2 = args.annotators.split(",")
    units = read(args.key)
    ref, first, current, source, missing, unexpected = build_reference(
        units, read(args.labels), read(args.adjudication), a1, a2)
    if missing or unexpected:
        raise SystemExit(f"Incomplete or inconsistent labels: missing={missing[:10]} unexpected={unexpected[:10]}")

    panel = {u["unit_id"]: u["panel_label"] for u in units}
    alt = {u["unit_id"]: any_capitulated(u) for u in units}
    result = {"config": {"key": str(args.key), "units": len(units), "bootstrap": BOOTSTRAP, "seed": SEED,
                         "reference_sources": source}}
    for name, weighted in (("sample", False), ("design_weighted", True)):
        result[name] = {
            "human_vs_human_first": weighted_score(units, first[a1], first[a2], weighted),
            "human_vs_human_current": weighted_score(units, current[a1], current[a2], weighted),
            "human_vs_human_first_by_language": by_language(units, first[a1], first[a2], weighted),
            "panel_vs_reference": weighted_score(units, ref, panel, weighted),
            "panel_vs_reference_by_language": by_language(units, ref, panel, weighted),
            "panel_vs_A1_current": weighted_score(units, current[a1], panel, weighted),
            "panel_vs_A2_current": weighted_score(units, current[a2], panel, weighted),
            "any_capitulated_vs_reference": weighted_score(units, ref, alt, weighted),
        }
    per_model = {}
    for model in sorted({u["model"] for u in units}):
        sub = [u for u in units if u["model"] == model]
        per_model[model] = {"units": len(sub),
                            "panel_agrees_with_reference": sum(panel[u["unit_id"]] == ref[u["unit_id"]] for u in sub),
                            "reference_labels": dict(collections.Counter(ref[u["unit_id"]] for u in sub)),
                            "panel_labels": dict(collections.Counter(panel[u["unit_id"]] for u in sub))}
    result["per_model_descriptive"] = per_model
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    def line(name, s):
        ci = "[{:.2f}, {:.2f}]".format(*s["ci95"]) if s["ci95"] else ""
        cap = s["classes"]["capitulated"]
        rec = f"{cap['recall']:.2f}" if cap["recall"] is not None else "-"
        pre = f"{cap['precision']:.2f}" if cap["precision"] is not None else "-"
        print(f"  {name:32s} {s['agreement']:6.1%}  kappa {s['kappa']:.3f} {ci:14s} capitulated recall {rec} precision {pre}")
    print(f"Reference: {source}")
    for name in ("sample", "design_weighted"):
        print(name)
        for k in ("human_vs_human_first", "human_vs_human_current", "panel_vs_reference",
                  "panel_vs_A1_current", "panel_vs_A2_current", "any_capitulated_vs_reference"):
            line(k, result[name][k])


if __name__ == "__main__":
    main()
