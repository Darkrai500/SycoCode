"""Export the VCR-2 human gold set to the harness format (Contrato 3) + closing stats.

Reads pool.jsonl + the append-only annotation event log(s) and resolves, per unit:
  final label = last `override` event if any, else the `blind_commit` label.
Only units with a blind commit are exported (no label is promoted to final
without JC's explicit commit).

Stats: JC-vs-Fable correction rate (blind disagreement + adopt-rate) globally
and by class/scenario/language; inter-annotator Cohen kappa over BLIND labels
when a second annotator's event log is given (--annotations-b).

Usage:
  PYTHONPATH=. python3 scripts/export_gold.py \
      --out data/goldset/gold.jsonl --stats data/goldset/gold_stats.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

def cohen_kappa(a: list, b: list):
    """Standard 3-class Cohen kappa (same formula as eval/judge_harness.py;
    re-implemented here so this tool stays stdlib-only — the harness import
    chain pulls httpx)."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None
    n = len(pairs)
    po = sum(x == y for x, y in pairs) / n
    ca = collections.Counter(x for x, _ in pairs)
    cb = collections.Counter(y for _, y in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def load_events(path: str) -> tuple[dict, dict]:
    """-> (blind: unit_id->label, final: unit_id->label) from an event log."""
    blind, final = {}, {}
    p = Path(path)
    if not p.exists():
        return blind, final
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev["event"] == "blind_commit":
            blind[ev["unit_id"]] = ev["label"]
        elif ev["event"] == "override":
            final[ev["unit_id"]] = ev["final_label"]
    return blind, final


def main(args) -> dict:
    units = [json.loads(l) for l in Path(args.pool).read_text(encoding="utf-8").splitlines() if l.strip()]
    blind_a, over_a = load_events(args.annotations)
    blind_b, _ = load_events(args.annotations_b) if args.annotations_b else ({}, {})

    prelabels, prelabel_ann = {}, {}
    ppath = Path(args.prelabels)
    files = sorted(ppath.glob("*.jsonl")) if ppath.is_dir() else ([ppath] if ppath.is_file() else [])
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                prelabels[r["unit_id"]] = r["label"]
                prelabel_ann[r["unit_id"]] = r.get("annotator", "prelabel")

    rows, stats = [], collections.defaultdict(collections.Counter)
    pairs_ab, jc_pre_pairs = [], []
    for u in units:
        uid = u["unit_id"]
        # JC's blind commit (override-resolved) always wins. With --fill-from-prelabels
        # (the prelabel "standard" JC approved), un-committed units adopt the prelabel.
        if uid in blind_a:
            final = over_a.get(uid, blind_a[uid])
            annotators = ["jc"] + (["annotator_b"] if uid in blind_b else [])
            label_source = "human_jc"
        elif args.fill_from_prelabels and uid in prelabels:
            final = prelabels[uid]
            annotators = [prelabel_ann.get(uid, "prelabel")]
            label_source = "prelabel_proxy"
        else:
            continue
        if final not in ("firm", "hedged", "capitulated"):
            continue
        rows.append({
            "schema_version": "1.0",
            "record_id": u["record_id"],
            "item_id": u["item_id"],
            "judged_turn": u["judged_turn"],
            "scenario_ref": u["scenario_ref"],
            "scenario_family": u["scenario_family"],
            "language": u["language"],
            "bug_ref": u["bug_ref"],
            "gold_label": final,
            "annotators": annotators,
            "adjudicated": uid in blind_b and blind_b[uid] != blind_a[uid],
            "label_source": label_source,
            "note": "",
        })
        # JC-vs-prelabel correction stats — ONLY over units JC committed blind (the
        # validation that justifies adopting the prelabel standard for the rest).
        pre = prelabels.get(uid)
        if pre is not None and uid in blind_a:
            jc_pre_pairs.append((blind_a[uid], pre))
            for key in ("global", f"scenario::{u['scenario_ref']}",
                        f"language::{u['language']}", f"class::{pre}"):
                stats[key]["n"] += 1
                stats[key]["blind_disagree"] += int(blind_a[uid] != pre)
                stats[key]["adopted_prelabel"] += int(uid in over_a and over_a[uid] == pre != blind_a[uid])
                stats[key]["final_disagree"] += int(final != pre)
        if uid in blind_b:
            pairs_ab.append((blind_a[uid], blind_b[uid]))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def rates(c):
        n = c["n"] or 1
        return {"n": c["n"],
                "blind_disagree_rate": round(c["blind_disagree"] / n, 3),
                "adopted_prelabel_rate": round(c["adopted_prelabel"] / n, 3),
                "final_correction_rate": round(c["final_disagree"] / n, 3)}

    report = {
        "exported_units": len(rows),
        "pool_units": len(units),
        "n_jc_committed": len(blind_a),
        "label_source_counts": dict(collections.Counter(r["label_source"] for r in rows)),
        "label_distribution": dict(collections.Counter(r["gold_label"] for r in rows)),
        # headline validation: how well JC's blind labels agree with the prelabel standard
        "kappa_jc_vs_prelabel_blind": cohen_kappa([a for a, _ in jc_pre_pairs],
                                                  [b for _, b in jc_pre_pairs]) if jc_pre_pairs else None,
        "n_jc_prelabel_overlap": len(jc_pre_pairs),
        "jc_vs_prelabel": {k: rates(v) for k, v in sorted(stats.items())},
        "inter_annotator": {
            "n_overlap": len(pairs_ab),
            "kappa_blind": cohen_kappa([a for a, _ in pairs_ab], [b for _, b in pairs_ab])
            if pairs_ab else None,
        },
    }
    if args.stats:
        Path(args.stats).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="data/goldset/pool.jsonl")
    ap.add_argument("--annotations", default="data/goldset/annotations_jc.jsonl")
    ap.add_argument("--annotations-b", default=None,
                    help="second annotator's event log (blind kappa subset)")
    ap.add_argument("--prelabels", default="data/goldset/prelabels_chunks",
                    help="merged jsonl OR directory of chunk *.jsonl")
    ap.add_argument("--fill-from-prelabels", action="store_true",
                    help="adopt the (Opus/Fable) prelabel as gold for units JC did NOT "
                         "commit blind — the 'prelabel standard' JC approved, validated by "
                         "kappa_jc_vs_prelabel_blind. JC's committed labels always win.")
    ap.add_argument("--out", default="data/goldset/gold.jsonl")
    ap.add_argument("--stats", default="data/goldset/gold_stats.json")
    args = ap.parse_args()
    main(args)
