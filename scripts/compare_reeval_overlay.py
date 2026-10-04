#!/usr/bin/env python3
"""Compare a partial-label sensitivity run with the frozen historical ledgers."""
import argparse
import gzip
import json
from pathlib import Path

from audit_reeval import dump, sha, unique


def ledger(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def differences(old, new, path=""):
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict) and old.keys() == new.keys():
        return [d for k in old for d in differences(old[k], new[k], path + "/" + k)]
    return [{"path": path, "historical": old, "partial_account_overlay": new}]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--overlay", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists() or a.out.is_symlink():
        ap.error("Output must be new")
    paths = [a.baseline / "item_ledger.jsonl.gz", a.overlay / "item_ledger.jsonl",
             a.baseline / "turn_ledger.jsonl.gz", a.overlay / "turn_ledger.jsonl",
             a.baseline / "statistics.json", a.overlay / "statistics.json",
             a.baseline / "validation.json", a.overlay / "validation.json"]
    before = {str(p.resolve()): sha(p) for p in paths}
    old_items, new_items = [unique(ledger(p), lambda r: (r["model"], r["record_id"])) for p in paths[:2]]
    old_turns, new_turns = [unique(ledger(p), lambda r: (r["model"], r["record_id"], r["turn"])) for p in paths[2:4]]
    if old_items.keys() != new_items.keys() or old_turns.keys() != new_turns.keys():
        raise ValueError("Ledger support changed")
    old_stats, new_stats, old_valid, new_valid = [json.loads(p.read_text()) for p in paths[4:]]
    if any(new_valid["input_sha256"].get(k) != v for k, v in old_valid["input_sha256"].items()):
        raise ValueError("Historical input hashes differ")
    output = {"status": "partial label sensitivity; interpretation depends on recorded label provenance; remaining cohort historical; no adjudication",
              "input_sha256": before, "historical_source_hashes_match": True,
              "overlaid_turns": new_valid["overlay_units"],
              "cohort_vcr_turns": sum(r["label"] is not None for r in old_turns.values()),
              "changed_vcr_turns": sum(old_turns[k]["label"] != r["label"] for k, r in new_turns.items()),
              "changed_final_labels": sum(old_items[k]["final_label"] != r["final_label"] for k, r in new_items.items()),
              "changed_functional_states": sum(sum(x != y for x, y in zip(old_items[k]["states"]["historical"], r["states"]["historical"])) for k, r in new_items.items()),
              "changed_functional_finals": sum(old_items[k]["states"]["historical"][-1] != r["states"]["historical"][-1] for k, r in new_items.items()),
              "statistics_changes": differences(old_stats, new_stats),
              "all_50_rounded_headline_values_equal": all(r["equal"] for r in new_valid["aggregate_checks"]),
              "script_sha256": sha(__file__)}
    if before != {str(p.resolve()): sha(p) for p in paths}:
        raise ValueError("Input mutation detected")
    output["inputs_unchanged"] = True
    dump(a.out, output)
    print(json.dumps({k: v for k, v in output.items() if k not in ("input_sha256", "statistics_changes")}, indent=2))


if __name__ == "__main__":
    main()
