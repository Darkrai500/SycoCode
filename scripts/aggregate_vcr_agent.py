"""Aggregate the vcr-annotator (Sonnet) verdict files into vcr_agent.jsonl.

Reads the annotation manifest + the per-turn verdict files written by the
`vcr-agent-eval` workflow, joins them back to the record metadata, and emits a
vcr.jsonl-shaped file (so downstream analysis treats it like any other judge).
Also reports the MISSING turn indices so the workflow can be re-run on just those.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/aggregate_vcr_agent.py \
      --manifest data/runs/vcr_manifest.json \
      --out-dir  data/runs/vcr_out --who a \
      --out      data/runs/vcr_agent.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LABELS = ["firm", "hedged", "capitulated"]
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
JUDGE_MODEL = "claude-vcr-annotator(sonnet)"


def _read_verdict(p: Path):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/runs/vcr_manifest.json")
    ap.add_argument("--out-dir", default="data/runs/vcr_out")
    ap.add_argument("--who", default="a")
    ap.add_argument("--out", default="data/runs/vcr_agent.jsonl")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    od = Path(args.out_dir)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows, missing, dist = [], [], Counter()
    for m in manifest:
        idx = m["idx"]
        v = _read_verdict(od / f"{args.who}_t{idx:05d}.json")
        if v is None:
            missing.append(idx)
            continue
        dist[v["label"]] += 1
        rows.append({
            "schema_version": "0.1.0", "record_id": m["record_id"], "item_id": m["item_id"],
            "scenario_ref": m.get("scenario_ref"), "scenario_family": m.get("scenario_family"),
            "language": m.get("language"), "bug_ref": m.get("bug_ref"),
            "judged_turn": m["judged_turn"], "judge_model": JUDGE_MODEL, "annotator": args.who,
            "label": v["label"], "language_switch": bool(v.get("language_switch")),
            "confidence": v.get("confidence"), "rationale": v.get("rationale"),
            "judged_at": now,
        })

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps({
        "manifest_turns": len(manifest),
        "labelled": len(rows),
        "missing_count": len(missing),
        "label_distribution": dict(dist),
        "out": args.out,
        "missing_idxs": missing,   # feed back as workflow args {"idxs": [...]} to re-run
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
