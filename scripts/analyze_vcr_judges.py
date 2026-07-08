"""Multi-judge VCR analysis for the cand_001 pilot, all vs a human-proxy gold:

    GLM-4.7 (Cerebras)  vs  gpt-oss-120b (Cerebras)  vs  DeepSeek-V4-Flash (W&B/CoreWeave)
    -------- each compared against the Claude/Opus human-proxy gold (a/b + adjudication) --

Human gold is built from two independent blind Opus annotators (ann_out/{a,b}_t*.json):
agreement -> gold; disagreement -> read from an adjudication file (idx -> label) that
the human evaluator (main-loop Opus) fills after reviewing the turn. Outputs agreement,
Cohen's kappa (3-class), confusion matrices, per-language / per-scenario VCR, and the
disagreement roster. Pure stdlib (no sklearn).

Usage:
  PYTHONPATH=. .venv/bin/python scripts/analyze_vcr_judges.py \
      --dir data/pilot/cand_001 --out data/pilot/cand_001/vcr_three_way.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ["firm", "hedged", "capitulated"]
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _read_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _read_ann(p: Path):
    """Tolerant read of an annotator's verdict file (strip fences/prose if any)."""
    try:
        txt = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    m = _JSON_RE.search(txt)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d if d.get("label") in LABELS else None


def agreement(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None, 0
    return sum(1 for x, y in pairs if x == y) / len(pairs), len(pairs)


def cohen_kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for x, y in pairs if x == y) / n
    ca = Counter(x for x, _ in pairs)
    cb = Counter(y for _, y in pairs)
    pe = sum((ca.get(l, 0) / n) * (cb.get(l, 0) / n) for l in set(ca) | set(cb))
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def confusion(ref, hyp):
    """rows = ref label, cols = hyp label."""
    cm = {r: {c: 0 for c in LABELS} for r in LABELS}
    for r, h in zip(ref, hyp):
        if r in LABELS and h in LABELS:
            cm[r][h] += 1
    return cm


def vcr_rate(labels):
    """Capitulation-centred summary over a label list (None ignored)."""
    ls = [l for l in labels if l in LABELS]
    n = len(ls) or 1
    c = Counter(ls)
    return {
        "n": len(ls),
        "firm": c["firm"], "hedged": c["hedged"], "capitulated": c["capitulated"],
        "capitulated_rate": round(c["capitulated"] / n, 3),
        "non_firm_rate": round((c["hedged"] + c["capitulated"]) / n, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/pilot/cand_001")
    ap.add_argument("--out", default="data/pilot/cand_001/vcr_three_way.json")
    args = ap.parse_args()
    d = Path(args.dir)

    manifest = json.loads((d / "ann_manifest.json").read_text(encoding="utf-8"))
    by_idx = {m["idx"]: m for m in manifest}
    key_of = {(m["record_id"], m["judged_turn"]): m["idx"] for m in manifest}

    # human annotators a, b
    ann = {"a": {}, "b": {}}
    for who in ("a", "b"):
        for idx in by_idx:
            v = _read_ann(d / "ann_out" / f"{who}_t{idx:02d}.json")
            if v:
                ann[who][idx] = v

    # adjudication of a/b disagreements (idx -> label), filled by the human evaluator
    adj_path = d / "ann_adjudication.json"
    raw_adj = json.loads(adj_path.read_text(encoding="utf-8")) if adj_path.is_file() else {}
    adj = {int(k): v for k, v in raw_adj.items() if k.isdigit() and v in LABELS}

    # build gold
    gold, disagreements, missing = {}, [], []
    for idx in by_idx:
        la = ann["a"].get(idx, {}).get("label")
        lb = ann["b"].get(idx, {}).get("label")
        if la is None or lb is None:
            missing.append(idx)
        if la and lb and la == lb:
            gold[idx] = la
        elif idx in adj:
            gold[idx] = adj[idx]
        else:
            if la and lb:
                disagreements.append({"idx": idx, "item_id": by_idx[idx]["item_id"],
                                      "judged_turn": by_idx[idx]["judged_turn"],
                                      "a": la, "b": lb})

    # judge labels, keyed by idx (tolerant of a missing judge file)
    def judge_by_idx(fname):
        out = {}
        p = d / fname
        if not p.is_file():
            return out
        for r in _read_jsonl(p):
            k = (r["record_id"], r["judged_turn"])
            if k in key_of:
                out[key_of[k]] = r.get("label")
        return out

    gpt = judge_by_idx("vcr_gptoss.jsonl")
    glm = judge_by_idx("vcr.jsonl")
    dsk = judge_by_idx("vcr_deepseek.jsonl")     # DeepSeek-V4-Flash via W&B/CoreWeave

    # prior independent Opus annotation (consistency check), keyed by (item_id, judged_turn)
    prior = {}
    vv = d / "vcr_validation.json"
    if vv.is_file():
        for r in json.loads(vv.read_text(encoding="utf-8")):
            k = (r.get("item_id"), r.get("judged_turn"))
            if k[0] is not None:
                prior[k] = r.get("opus_label")
    prior_by_idx = {m["idx"]: prior.get((m["item_id"], m["judged_turn"])) for m in manifest}

    idxs = sorted(by_idx)
    g = [gold.get(i) for i in idxs]
    G = [gpt.get(i) for i in idxs]
    L = [glm.get(i) for i in idxs]
    D = [dsk.get(i) for i in idxs]
    A = [ann["a"].get(i, {}).get("label") for i in idxs]
    B = [ann["b"].get(i, {}).get("label") for i in idxs]
    P = [prior_by_idx.get(i) for i in idxs]

    def pair(ref, hyp):
        ag, n = agreement(ref, hyp)
        return {"agreement": None if ag is None else round(ag, 3), "n": n,
                "cohen_kappa": cohen_kappa(ref, hyp), "confusion_ref_rows": confusion(ref, hyp)}

    # per-language slices vs gold
    def by_lang(hyp):
        out = {}
        for lang in ("en", "es"):
            sel = [i for i in idxs if by_idx[i]["language"] == lang]
            ag, n = agreement([gold.get(i) for i in sel], [hyp.get(i) for i in sel])
            out[lang] = {"agreement": None if ag is None else round(ag, 3), "n": n,
                         "cohen_kappa": cohen_kappa([gold.get(i) for i in sel], [hyp.get(i) for i in sel])}
        return out

    # per-scenario VCR (gold)
    fam_vcr = {}
    for fam in sorted({m["scenario_family"] for m in manifest}):
        sel = [i for i in idxs if by_idx[i]["scenario_family"] == fam]
        fam_vcr[fam] = {
            "gold": vcr_rate([gold.get(i) for i in sel]),
            "gpt_oss": vcr_rate([gpt.get(i) for i in sel]),
            "glm": vcr_rate([glm.get(i) for i in sel]),
            "deepseek": vcr_rate([dsk.get(i) for i in sel]),
        }

    report = {
        "n_turns": len(idxs),
        "gold_resolved": len(gold),
        "gold_missing_annotation": missing,
        "n_disagreements_a_b": len(disagreements),
        "disagreements_a_b": disagreements,
        "inter_annotator_opus": {**pair(A, B)},
        "fresh_vs_prior_opus": pair(P, A),  # sanity: new annotator a vs prior validation
        "headline_vs_gold": {
            "gpt_oss_120b": pair(g, G),
            "glm_4_7": pair(g, L),
            "deepseek_v4_flash": pair(g, D),
        },
        "judge_vs_judge": {
            "gpt_oss_vs_glm": pair(G, L),
            "deepseek_vs_glm": pair(D, L),
            "deepseek_vs_gpt_oss": pair(D, G),
        },
        "per_language_vs_gold": {"gpt_oss": by_lang(gpt), "glm": by_lang(glm),
                                 "deepseek": by_lang(dsk)},
        "vcr_distribution": {
            "gold": vcr_rate(g), "gpt_oss": vcr_rate(G), "glm": vcr_rate(L),
            "deepseek": vcr_rate(D),
            "annotator_a": vcr_rate(A), "annotator_b": vcr_rate(B),
        },
        "per_scenario_family_vcr": fam_vcr,
    }

    # also dump the resolved gold as jsonl for the report appendix
    with open(d / "human_gold.jsonl", "w", encoding="utf-8") as fh:
        for i in idxs:
            m = by_idx[i]
            fh.write(json.dumps({
                "idx": i, "item_id": m["item_id"], "judged_turn": m["judged_turn"],
                "language": m["language"], "scenario_family": m["scenario_family"],
                "bug_present": m["bug_present"], "gold": gold.get(i),
                "annotator_a": ann["a"].get(i, {}).get("label"),
                "annotator_b": ann["b"].get(i, {}).get("label"),
                "gpt_oss": gpt.get(i), "glm": glm.get(i), "deepseek": dsk.get(i),
            }, ensure_ascii=False) + "\n")

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
