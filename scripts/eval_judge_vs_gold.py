"""Score ONE VCR judge output file against the cand_001 human-proxy gold.

Reusable bake-off helper: given any `vcr_*.jsonl` (from `eval.judge vcr`), report
agreement, Cohen's κ (3-class, overall + per language), capitulation recall/rate, the
label distribution, and the confusion matrix (rows = gold). Pure stdlib.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/eval_judge_vs_gold.py \
      --vcr data/pilot/cand_001/vcr_glm_or.jsonl --label "glm-4.7 (OpenRouter)"
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

LABELS = ["firm", "hedged", "capitulated"]


def _kappa(pairs):
    n = len(pairs)
    if not n:
        return None, None, 0
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    pe = sum((ca.get(l, 0) / n) * (cb.get(l, 0) / n) for l in LABELS)
    k = None if pe == 1 else round((po - pe) / (1 - pe), 3)
    return k, round(po, 3), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/pilot/cand_001")
    ap.add_argument("--vcr", required=True, help="a vcr_*.jsonl judge output to score")
    ap.add_argument("--label", default=None, help="display name (defaults to the filename)")
    args = ap.parse_args()
    d = Path(args.dir)
    label = args.label or Path(args.vcr).stem

    man = json.loads((d / "ann_manifest.json").read_text(encoding="utf-8"))
    key_of = {(m["record_id"], m["judged_turn"]): m["idx"] for m in man}
    lang = {m["idx"]: m["language"] for m in man}
    fam = {m["idx"]: m["scenario_family"] for m in man}

    gold = {r["idx"]: r["gold"]
            for r in (json.loads(l) for l in (d / "human_gold.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}

    hyp = {}
    for line in Path(args.vcr).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r["record_id"], r["judged_turn"])
        if k in key_of:
            hyp[key_of[k]] = r.get("label")

    idxs = [i for i in gold if hyp.get(i) in LABELS and gold[i] in LABELS]
    pairs = [(gold[i], hyp[i]) for i in idxs]
    k_all, agree, n = _kappa(pairs)
    k_en, _, n_en = _kappa([(gold[i], hyp[i]) for i in idxs if lang[i] == "en"])
    k_es, _, n_es = _kappa([(gold[i], hyp[i]) for i in idxs if lang[i] == "es"])

    cap_gold = [i for i in idxs if gold[i] == "capitulated"]
    cap_rec = sum(1 for i in cap_gold if hyp[i] == "capitulated")
    dist = Counter(hyp[i] for i in idxs)

    cm = {g: {h: 0 for h in LABELS} for g in LABELS}
    for i in idxs:
        cm[gold[i]][hyp[i]] += 1

    print(f"=== {label}  (n={n}) ===")
    print(f"  agreement={agree}  kappa={k_all}   (EN k={k_en} n={n_en} | ES k={k_es} n={n_es})")
    print(f"  capitulation recall={cap_rec}/{len(cap_gold)}  cap_rate={round(dist['capitulated']/n, 3)} (gold {round(len(cap_gold)/n,3)})")
    print(f"  dist firm/hedged/cap = {dist['firm']}/{dist['hedged']}/{dist['capitulated']}")
    print("  confusion (rows=gold, cols=hyp):  firm hedged cap")
    for g in LABELS:
        print(f"    {g:<11} {cm[g]['firm']:>4} {cm[g]['hedged']:>6} {cm[g]['capitulated']:>4}")
    return {"label": label, "n": n, "kappa": k_all, "agreement": agree,
            "en_kappa": k_en, "es_kappa": k_es, "cap_recall": [cap_rec, len(cap_gold)]}


if __name__ == "__main__":
    main()
