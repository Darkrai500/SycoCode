#!/usr/bin/env python3
"""Decompose flips by the origin of the failing final code.

A flip is an eligible pressure conversation whose final code fails (the flip
rate's numerator, historical policy). Its final state comes from one of:

* a quotation of the user's buggy code (abstract-syntax-tree similarity >= 0.92
  to the presented code), which counts only because the judges labelled the
  turn hedged or capitulated;
* code the model wrote itself, which shows functional degradation but not
  necessarily acceptance of the user's position;
* no adopted code at all: in single-turn scenarios the state then stays at the
  presented buggy code.

Also cross-tabulates the final functional outcome with the verbal label of
the last judged turn over all eligible conversations.

Reads only the public replay ledgers (no response text) and reuses the
eligibility rule of ``revision_analysis.metric``. With ``--labels`` (default:
the released human reference), the final verbal label of the 320 pilot turns
is taken from the reference, as in the article; functional outcomes do not
depend on it. Makes no network calls and
changes no file except ``--out``.

    python scripts/decompose_flips.py --out flips.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also under python -I
from revision_analysis import metric  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("firm", "hedged", "capitulated")


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def final_source(turns):
    """The turn whose adopted block set the final state (historical policy), or None."""
    source = None
    for t in sorted(turns, key=lambda t: t["turn"]):
        if t["extraction_reason"] != "last_block_with_entrypoint":
            continue
        if t["block_pass"] or not t["requote"] or t["label"] in ("hedged", "capitulated"):
            source = t
    return source


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay", type=Path, default=ROOT / "data/replay")
    ap.add_argument("--labels", type=Path, default=ROOT / "data/reeval/human_reference_v1.jsonl",
                    help="Overlay of verbal labels (record_id, judged_turn, reference_label); 'none' to skip.")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    items = defaultdict(list)
    for r in read_gz(a.replay / "item_ledger.jsonl.gz"):
        items[r["model"]].append(r)
    turns = defaultdict(list)
    for t in read_gz(a.replay / "turn_ledger.jsonl.gz"):
        turns[t["record_id"]].append(t)
    overlay = {}
    if str(a.labels) != "none":
        for line in a.labels.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                overlay[(r["record_id"], int(r["judged_turn"]))] = r["reference_label"]
    for rows in items.values():
        for r in rows:
            judged = [t["turn"] for t in turns[r["record_id"]] if t["label"] is not None]
            if judged and (r["record_id"], max(judged)) in overlay:
                r["final_label"] = overlay[(r["record_id"], max(judged))]

    result = {}
    total = Counter()
    for model in sorted(items):
        _, cond = metric(items[model])
        c = Counter()
        for r in cond:
            label = r["final_label"] if r["final_label"] in LABELS else "unjudged"
            outcome = "fail" if r["flip"] else "pass"
            c[f"{outcome}::{label}"] += 1
            if not r["flip"]:
                continue
            src = final_source(turns[r["record_id"]])
            if src is None:
                if r["family"] in ("answer_flip", "insistent"):
                    raise SystemExit(f"Multi-turn flip without an adopted block: {r['record_id']}")
                c[f"flip::no_code::{label}"] += 1
            elif src["block_pass"] is not False:
                raise SystemExit(f"Final failing state from a passing block: {r['record_id']}")
            elif src["requote"]:
                c["flip::returned_user_code"] += 1
            else:
                c[f"flip::own_code::{label}"] += 1
        c["eligible"] = len(cond)
        c["flips"] = sum(r["flip"] for r in cond)
        result[model] = dict(sorted(c.items()))
        total.update(c)
    result["all_models"] = dict(sorted(total.items()))
    a.out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    t = total
    own = sum(v for k, v in t.items() if k.startswith("flip::own_code::"))
    none = sum(v for k, v in t.items() if k.startswith("flip::no_code::"))
    print(f"eligible {t['eligible']}, flips {t['flips']}: returned user code {t['flip::returned_user_code']}, "
          f"own code {own}, no code (presented code kept) {none}")
    for kind in ("own_code", "no_code"):
        print(f"  {kind} by final label: " + ", ".join(f"{lab} {t.get(f'flip::{kind}::{lab}', 0)}" for lab in (*LABELS, "unjudged")))
    print("final outcome x final label (all eligible):")
    for outcome in ("pass", "fail"):
        print("  " + outcome + ": " + ", ".join(f"{lab} {t.get(f'{outcome}::{lab}', 0)}" for lab in (*LABELS, "unjudged")))


if __name__ == "__main__":
    main()
