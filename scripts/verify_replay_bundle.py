#!/usr/bin/env python3
"""Check every bundle hash and ledger relationship, then replay saved statistics."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

DATA_FILES = ("item_ledger.jsonl.gz", "turn_ledger.jsonl.gz", "statistics.json")
PAYLOAD = {
    "README.md", "LICENSE.txt", "requirements.txt", "PROVENANCE.json",
    "scripts/revision_analysis.py", "scripts/revision_replay_ledgers.py",
    "scripts/verify_replay_bundle.py", "scripts/offline_guard.py",
    *("data/" + name for name in DATA_FILES),
}
MODELS = {"full", "gemini-3-1-flash-lite", "gemini-3-5-flash", "glm-5-2",
          "kimi-k-2-6", "claude-opus-4-8", "claude-sonnet-4-6", "gpt-5-5",
          "gpt-5-4-mini", "minimax-m3"}
POLICIES = {"historical", "cap_only", "no_requotes", "all_extracted",
            "exclude_requotes", "exclude_execution_errors", "require_final_code",
            "first_entrypoint", "last_fence"}
COMMON = {"model", "record_id", "item_id", "problem", "bug", "scenario",
          "family", "language", "response_line"}
ITEM_FIELDS = COMMON | {"source", "category", "level", "bug_present", "requotes",
                       "error_turns", "final_code_extracted", "final_label", "states"}
TURN_FIELDS = COMMON | {"turn", "label", "code_sha256", "extraction_reason", "requote",
                       "block_pass", "effective_pass", "error_class", "policy_pass"}
LABELS = {None, "firm", "hedged", "capitulated"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_file(root, relative):
    path = root / relative
    require(path.is_file() and not path.is_symlink(), f"missing/linked file: {relative}")
    require(path.absolute() == path.resolve(), f"redirected file: {relative}")
    return path


def verify_manifest(root):
    root = root.resolve()
    manifest = json.loads(checked_file(root, "manifest.json").read_text())
    require(manifest.get("schema_version") == 1, "unsupported manifest version")
    files = manifest.get("files", [])
    names = [f["path"] for f in files]
    require(len(names) == len(set(names)) and set(names) == PAYLOAD,
            "manifest does not match the fixed payload allowlist")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if not p.is_dir()}
    require(actual == PAYLOAD | {"manifest.json"}, "unexpected or missing bundle files")
    require(not any(p.is_symlink() for p in root.rglob("*")), "symlinks are not allowed")
    for entry in files:
        path = checked_file(root, entry["path"])
        require(path.stat().st_size == entry["bytes"] and digest(path) == entry["sha256"],
                f"integrity mismatch: {entry['path']}")
    return {"files_checked": len(files), "manifest_sha256": digest(root / "manifest.json")}


def read_ledger(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def validate_ledgers(root):
    items = read_ledger(checked_file(root, DATA_FILES[0]))
    turns = read_ledger(checked_file(root, DATA_FILES[1]))
    require(len(items) == 19000 and len(turns) == 34000, "ledger row coverage mismatch")
    by_record, by_item = {}, set()
    for row in items:
        require(set(row) == ITEM_FIELDS, "unexpected item fields (possible text payload)")
        key = row["model"], row["record_id"]
        item = row["model"], row["item_id"]
        require(key not in by_record and item not in by_item, "duplicate conversation")
        require(row["model"] in MODELS and row["language"] in {"en", "es"}, "invalid item scope")
        require(row["final_label"] in LABELS, "invalid final label")
        require(set(row["states"]) == POLICIES, "unexpected policy keys")
        count = 5 if row["family"] == "insistent" else 2 if row["family"] == "answer_flip" else 1
        for states in row["states"].values():
            require(len(states) == count and all(x is None or type(x) is bool for x in states),
                    "invalid policy states")
        by_record[key] = row
        by_item.add(item)
    seen = set()
    for row in turns:
        require(set(row) == TURN_FIELDS, "unexpected turn fields (possible text payload)")
        key = row["model"], row["record_id"]
        require(key in by_record, "orphan turn")
        parent = by_record[key]
        require(all(row[k] == parent[k] for k in COMMON), "turn/conversation metadata mismatch")
        turn = row["turn"]
        require(type(turn) is int and 1 <= turn <= len(parent["states"]["historical"]), "invalid turn")
        require((*key, turn) not in seen, "duplicate turn")
        seen.add((*key, turn))
        require(row["label"] in LABELS, "invalid turn label")
        judged = parent["family"] != "control" and (len(parent["states"]["historical"]) == 1 or turn > 1)
        require((row["label"] is not None) == judged, "label coverage mismatch")
        require(row["code_sha256"] is None or re.fullmatch(r"[0-9a-f]{64}", row["code_sha256"]),
                "invalid code digest")
        require(set(row["policy_pass"]) == POLICIES, "unexpected turn policies")
        for policy, value in row["policy_pass"].items():
            require((value is None or type(value) is bool) and value is parent["states"][policy][turn - 1],
                    "turn/conversation state mismatch")
        require(row["effective_pass"] is row["policy_pass"]["historical"], "effective state mismatch")
        if turn == len(parent["states"]["historical"]):
            require(row["label"] == parent["final_label"], "final label mismatch")
    expected_turns = sum(len(r["states"]["historical"]) for r in items)
    require(len(seen) == expected_turns, "missing turn")
    require(Counter(r["model"] for r in items) == Counter({m: 1900 for m in MODELS}), "model item coverage")
    require(Counter(r["model"] for r in turns) == Counter({m: 3400 for m in MODELS}), "model turn coverage")
    item_sets = [{r["item_id"] for r in items if r["model"] == m} for m in sorted(MODELS)]
    require(all(s == item_sets[0] for s in item_sets), "models do not share the same item set")
    problem_sets = [{r["problem"] for r in items if r["model"] == m} for m in sorted(MODELS)]
    require(len(problem_sets[0]) == 50 and all(s == problem_sets[0] for s in problem_sets), "problem coverage")
    expected = json.loads(checked_file(root, "statistics.json").read_text())
    require(expected["config"]["B"] == 10000 and expected["config"]["seed"] == 20260919,
            "unexpected historical resampling configuration")
    require(set(expected["models"]) == MODELS, "statistics model coverage")
    return {"conversations": len(items), "turns": len(turns), "models": len(MODELS),
            "problems": 50, "labelled_turns": sum(r["label"] is not None for r in turns)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True, help="new directory outside the bundle")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    if out.exists() or args.out.is_symlink() or out.is_relative_to(root):
        parser.error("output must be a new directory outside the bundle")
    try:
        report = {"manifest": verify_manifest(root), "coverage": validate_ledgers(root / "data")}
        require(sys.version_info[:2] == (3, 12), "the replay profile requires CPython 3.12")
        numpy_version = importlib.metadata.version("numpy")
        require(numpy_version == "2.0.2", "install NumPy 2.0.2 from the supplied hashed requirements")
        report["environment"] = {"python": platform.python_version(), "numpy": numpy_version,
                                 "platform": platform.platform(), "machine": platform.machine()}
        env = {k: os.environ[k] for k in ("PATH", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT") if k in os.environ}
        proc = subprocess.run([sys.executable, "-B", "-I", str(root / "scripts/offline_guard.py"),
                               str(root / "scripts/revision_replay_ledgers.py"),
                               "--evidence-root", str(root / "data"), "--out", str(out)],
                              cwd=root, env=env, text=True, capture_output=True, timeout=300)
        require(proc.returncode == 0, "statistics replay failed: " + proc.stdout + proc.stderr)
        require("SYCO_NETWORK_ATTEMPTS=0" in proc.stdout, "unexpected network attempt")
        validation = json.loads((out / "validation.json").read_text())
        require(validation["statistics_structured_equal"], "statistics differ")
        require(report["manifest"] == verify_manifest(root), "bundle changed during replay")
        report.update(statistics_structured_equal=True, inputs_unchanged=True, network_attempts=0)
        (out / "bundle_validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    except (ValueError, KeyError, TypeError, OSError, importlib.metadata.PackageNotFoundError,
            subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"bundle verification failed: {exc}\n")


if __name__ == "__main__":
    main()
