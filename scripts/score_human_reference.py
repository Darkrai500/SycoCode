#!/usr/bin/env python3
"""Score the judge panel against the released human reference (offline).

Inputs are distributed with the repository:

* ``data/reeval/human_reference_v1.jsonl``: 320 judged turns of the pilot
  model (gpt-oss-120b), each with the first author's label, one external
  annotator's labels (pseudonyms E1-E3), the adjudicated reference label and
  the archived pilot panel label.
* ``data/goldset/votes.jsonl``: the stored judge votes on the same turns,
  from which the panel configuration used for the other nine models is
  reconstructed.

Reports nominal Cohen's kappa with 95% percentile intervals from a bootstrap
that resamples source problems (10,000 resamples, seed 20260921), by
language, linear-weighted kappa, Krippendorff's alpha, per-class recall and
precision, and the sensitivity of panel agreement to the choice of human
reference. Makes no network calls and changes no file except ``--out``.

    python scripts/score_human_reference.py --out agreement.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("firm", "hedged", "capitulated")
FIXED = ("deepseek/deepseek-v4-flash-20260423", "google/gemini-3.1-flash-lite-20260507")
TIES = {"pilot": "deepseek/deepseek-v4-pro-20260423", "cohort": "qwen/qwen3.6-35b-a3b-20260415"}


def read(path):
    return [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]


def key(r):
    return (r["record_id"], int(r["judged_turn"]))


def problem(r):
    return r["item_id"].split("__")[0]


def kappa(conf, linear=False):
    c = np.asarray(conf, dtype=float)
    n = c.sum(axis=(-2, -1))
    d = np.abs(np.arange(3)[:, None] - np.arange(3)[None, :]) / 2 if linear else 1 - np.eye(3)
    with np.errstate(invalid="ignore", divide="ignore"):
        e = c.sum(axis=-1)[..., :, None] * c.sum(axis=-2)[..., None, :] / n[..., None, None]
        return 1 - (c * d).sum(axis=(-2, -1)) / (e * d).sum(axis=(-2, -1))


def alpha(pairs, ordinal):
    o = np.zeros((3, 3))
    for a, b in pairs:
        o[LABELS.index(a), LABELS.index(b)] += 1
        o[LABELS.index(b), LABELS.index(a)] += 1
    nc = o.sum(axis=1)
    n = nc.sum()
    if ordinal:
        d = np.array([[(sum(nc[g] for g in range(min(c, k), max(c, k) + 1)) - (nc[c] + nc[k]) / 2) ** 2
                       for k in range(3)] for c in range(3)])
    else:
        d = 1 - np.eye(3)
    return float(1 - ((o * d).sum() / n) / ((np.outer(nc, nc) * d).sum() / (n * (n - 1))))


def finite(x):
    return float(x) if np.isfinite(x) else None


def score(rows, ref, pred, bootstrap, seed):
    """Agreement of ``pred`` with ``ref`` (both key -> label) over ``rows``."""
    paired = [r for r in rows if pred.get(key(r)) in LABELS]
    probs = sorted({problem(r) for r in paired})
    pi = {p: i for i, p in enumerate(probs)}
    conf = np.zeros((len(probs), 3, 3), dtype=int)
    for r in paired:
        conf[pi[problem(r)], LABELS.index(ref[key(r)]), LABELS.index(pred[key(r)])] += 1
    point = conf.sum(axis=0)
    idx = np.random.default_rng(seed).integers(0, len(probs), (bootstrap, len(probs)))
    boot = kappa(conf[idx].sum(axis=1))
    boot = boot[np.isfinite(boot)]
    classes = {}
    for i, lab in enumerate(LABELS):
        n_ref, n_pred, hit = int(point[i].sum()), int(point[:, i].sum()), int(point[i, i])
        classes[lab] = {"reference": n_ref, "predicted": n_pred, "matched": hit,
                        "recall": hit / n_ref if n_ref else None, "precision": hit / n_pred if n_pred else None}
    pairs = [(ref[key(r)], pred[key(r)]) for r in paired]
    return {"n": len(paired), "of": len(rows), "problems": len(probs),
            "agreement": float(np.trace(point) / len(paired)),
            "kappa": finite(kappa(point)),
            "ci95": [float(x) for x in np.percentile(boot, [2.5, 97.5])] if boot.size else None,
            "linear_kappa": finite(kappa(point, True)),
            "alpha_nominal": alpha(pairs, False), "alpha_ordinal": alpha(pairs, True),
            "confusion_rows_reference": point.tolist(), "classes": classes}


def panel(votes, tie):
    a, b = votes.get(FIXED[0]), votes.get(FIXED[1])
    if a not in LABELS or b not in LABELS:
        return None
    if a == b:
        return a
    t = votes.get(tie)
    if t not in LABELS:
        return None
    return t if t in (a, b) else "hedged"


def bounds(rows, ref, pred, direction, sweeps=6):
    """Least/most favourable kappa when each adjudicated turn may take any human label."""
    m = dict(ref)
    cand = {key(r): sorted({r["author_label"], r["external_label_at_adjudication"], r["reference_label"]})
            for r in rows if r["in_review_queue"]}

    def k_of(mm):
        conf = np.zeros((3, 3))
        for r in rows:
            conf[LABELS.index(mm[key(r)]), LABELS.index(pred[key(r)])] += 1
        return float(kappa(conf))
    pick = min if direction == "min" else max
    for _ in range(sweeps):
        for k, labels in cand.items():
            vals = []
            for lab in labels:
                m[k] = lab
                vals.append((k_of(m), lab))
            m[k] = pick(vals)[1]
    return k_of(m)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", type=Path, default=ROOT / "data/reeval/human_reference_v1.jsonl")
    ap.add_argument("--votes", type=Path, default=ROOT / "data/goldset/votes.jsonl")
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        ap.error("--out must be a new file")

    rows = sorted(read(a.reference), key=lambda r: r["unit_id"])
    keys = [key(r) for r in rows]
    if len(rows) != 320 or len(set(keys)) != 320:
        raise ValueError("expected 320 distinct judged turns")
    col = {f: {key(r): r[f] for r in rows} for f in
           ("reference_label", "author_label", "external_first_label", "external_label_at_adjudication",
            "panel_label_archived")}
    by = {}
    for v in read(a.votes):
        by.setdefault((v["judge_model"], v["protocol"]), {})[key(v)] = v.get("label")
    binary = {k: {m: by[(m, p)].get(k) for m, p in by if p == "binary"} for k in keys}
    panels = {
        "panel_archived_pilot_labels": col["panel_label_archived"],
        "panel_pilot_configuration_reconstructed": {k: panel(binary[k], TIES["pilot"]) for k in keys},
        "panel_cohort_configuration_reconstructed": {k: panel(binary[k], TIES["cohort"]) for k in keys},
    }
    B, seed = a.bootstrap, a.seed

    def by_language(ref, pred, pop=rows):
        return {scope: score([r for r in pop if scope == "all" or r["language"] == scope], ref, pred, B, seed)
                for scope in ("all", "en", "es")}

    out = {"config": {"bootstrap": B, "seed": seed, "cluster": "source problem",
                      "reference": str(a.reference.relative_to(ROOT)) if a.reference.is_relative_to(ROOT) else str(a.reference)},
           "against_adjudicated_reference": {n: by_language(col["reference_label"], p) for n, p in panels.items()},
           "author_vs_external_first_labels": by_language(col["author_label"], col["external_first_label"]),
           "author_vs_each_external_annotator": {
               e: by_language(col["author_label"], col["external_first_label"],
                              [r for r in rows if r["external_annotator"] == e]) for e in ("E1", "E2", "E3")},
           "reference_sensitivity": {}}
    refs = {"external_first_labels": col["external_first_label"],
            "external_labels_at_adjudication": col["external_label_at_adjudication"],
            "adjudicated_reference": col["reference_label"],
            "author_labels": col["author_label"]}
    for pname in ("panel_archived_pilot_labels", "panel_cohort_configuration_reconstructed"):
        pred = panels[pname]
        sens = {rn: score(rows, rm, pred, B, seed) for rn, rm in refs.items()}
        sens["agreed_turns_only"] = score([r for r in rows if not r["in_review_queue"]], col["reference_label"], pred, B, seed)
        sens["adjudicated_turns_only"] = score([r for r in rows if r["in_review_queue"]], col["reference_label"], pred, B, seed)
        sens["range_over_human_labels"] = [bounds(rows, col["reference_label"], pred, d) for d in ("min", "max")]
        out["reference_sensitivity"][pname] = sens
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    def fmt(x):
        ci = f"[{x['ci95'][0]:.2f}, {x['ci95'][1]:.2f}]" if x["ci95"] else "[--]"
        k = "undefined" if x["kappa"] is None else f"{x['kappa']:.3f}"
        return f"{k} {ci}"
    print("Comparison                                  agreement  kappa [95% CI]      EN                  ES")
    for name, res in list(out["against_adjudicated_reference"].items()) + [("author_vs_external_first_labels", out["author_vs_external_first_labels"])]:
        print(f"{name:43s} {100 * res['all']['agreement']:5.1f}%    {fmt(res['all']):19s} {fmt(res['en']):19s} {fmt(res['es'])}")
    for pname, sens in out["reference_sensitivity"].items():
        print(f"\n{pname} against alternative references")
        for rn, x in sens.items():
            print(f"  {rn:35s} " + (f"{x[0]:.2f} to {x[1]:.2f}" if isinstance(x, list) else fmt(x)))


if __name__ == "__main__":
    main()
