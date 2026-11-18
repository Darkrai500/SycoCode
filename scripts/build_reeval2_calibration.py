#!/usr/bin/env python3
"""Select the ReEval-2 calibration turns from the first human reference (fixed seed).

Only turns where the external annotator's label (first and current) and the
author's label coincide are eligible; adjudicated turns are excluded, and no
rationale is written, so nothing transmits the first author's reasoning. One
turn per conversation. The file holds the conversation as the annotators saw it,
without model identity, and is read-only for the app: answers are never stored.

    python scripts/build_reeval2_calibration.py \
        --reference ../SycoCode-release/data/reeval/human_reference_v1.jsonl \
        --out webapp/annotations/data/reeval2_calibration.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eval.verbal import strip_code  # noqa: E402
from scripts.gold_annotator import parse_payload  # noqa: E402

SEED = 20261104
SINGLE_TURN = {"code_review_sycophancy", "expertise_deference_senior", "expertise_deference_student"}
PER_STRATUM = 2  # per (label, language), so at most 12 turns; a thin stratum gives fewer but never none
# Two single-turn cases, read by hand, that teach the protocol's rule; every other turn comes from the seed.
# u0090 rejects the user's position and names the central bug. u0154 accepts it.
SINGLE_TURN_STRATA = {("firm", "en"), ("capitulated", "es")}
SINGLE_TURN_UNITS = {"u0090", "u0154"}


def eligible(row: dict) -> bool:
    return (row["label_source"] == "pair_agreement" and row["author_label"] == row["reference_label"]
            and row["external_first_label"] == row["reference_label"]
            and row["external_label_at_adjudication"] == row["reference_label"])


def choose(rows: list[dict], pool: dict[str, dict]) -> list[dict]:
    chosen, used = [], set()
    for label in ("firm", "hedged", "capitulated"):
        for language in ("en", "es"):
            stratum = sorted((r for r in rows if eligible(r) and r["reference_label"] == label and r["language"] == language),
                             key=lambda r: r["unit_id"])
            random.Random(f"{SEED}:{label}:{language}").shuffle(stratum)
            single = [r for r in stratum if r["scenario"] in SINGLE_TURN and r["unit_id"] in SINGLE_TURN_UNITS]
            multi = [r for r in stratum if r["scenario"] not in SINGLE_TURN]
            order = (single[:1] if (label, language) in SINGLE_TURN_STRATA else []) + multi
            picked = 0
            for row in order:
                group = pool[row["unit_id"]]["group_id"]
                if picked < PER_STRATUM and group not in used:
                    chosen.append(row)
                    used.add(group)
                    picked += 1
            if not picked:
                raise SystemExit(f"Not enough turns for {label}/{language}")
    return sorted(chosen, key=lambda r: hashlib.sha256(f"{SEED}:{r['unit_id']}".encode()).hexdigest())


def render(row: dict, unit: dict) -> dict:
    anchor, turns = parse_payload((ROOT / unit["payload_path"]).read_text(encoding="utf-8"))
    shown = []
    for turn in turns:
        if turn["turn"] > row["judged_turn"]:
            break
        judged = turn["role"] == "assistant" and turn["turn"] == row["judged_turn"]
        shown.append({"role": turn["role"], "turn": turn["turn"], "judged": judged, "text": strip_code(turn["text"]).text})
    return {"anchor": anchor, "turns": shown}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--pool", type=Path, default=ROOT / "data/goldset/pool.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "webapp/annotations/data/reeval2_calibration.json")
    args = ap.parse_args()
    rows = [json.loads(s) for s in args.reference.read_text(encoding="utf-8").splitlines() if s.strip()]
    pool = {u["unit_id"]: u for u in map(json.loads, args.pool.read_text(encoding="utf-8").splitlines())}
    cases = []
    for number, row in enumerate(choose(rows, pool), start=1):
        cases.append({"id": f"c{number:02d}", "language": row["language"], "label": row["reference_label"],
                      "single_turn": row["scenario"] in SINGLE_TURN, "source_unit": row["unit_id"],
                      **render(row, pool[row["unit_id"]])})
    args.out.write_text(json.dumps({"schema_version": "sycocode-reeval2-calibration-v1", "seed": SEED,
                                    "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
                                    "cases": cases}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases, {sum(c['single_turn'] for c in cases)} single-turn -> {args.out}")


if __name__ == "__main__":
    main()
