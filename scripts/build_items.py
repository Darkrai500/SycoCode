#!/usr/bin/env python3
"""
build_items.py — generate Layer-3 items.jsonl as the deterministic Cartesian
product of problems × scenarios × {bug variants | canonical} × languages.

Buggy scenarios render each of a problem's 3 bug variants; the clean control
(scenario with code_condition="canonical") renders the problem's canonical
solution once, with bug_present=false (the false-positive baseline). With 6
buggy scenarios and 1 clean control over 50 problems:
    50 × 2 × (3 × 6  +  1 × 1) = 1,900 items.

Items are NEVER hand-written. The grading oracle is NOT embedded (it lives in
problems.jsonl, joined via problem_ref + bug_ref).

Run from repo root:  PYTHONPATH=scripts python3 scripts/build_items.py
"""
import json, os, hashlib

HERE = os.path.dirname(__file__)
PROBLEMS = os.path.join(HERE, "..", "data", "problems", "problems.jsonl")
SCENARIOS = os.path.join(HERE, "..", "data", "problems", "scenarios.jsonl")
OUT = os.path.join(HERE, "..", "data", "problems", "items.jsonl")
SCHEMA = os.path.join(HERE, "..", "schema", "items.schema.json")
SCHEMA_VERSION = "0.2.0"

def _load(path):
    return [json.loads(l) for l in open(path) if l.strip()]

def _hash(item):
    payload = {k: v for k, v in item.items() if k != "content_hash"}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()

def build():
    problems = _load(PROBLEMS)
    scenarios = _load(SCENARIOS)
    items = []
    for p in problems:
        for sc in scenarios:
            cond = sc.get("code_condition", "buggy")
            if cond == "canonical":
                # one clean item per (problem, language): the canonical, no bug
                slots = [("canonical", p["canonical_solution"], None)]
            else:
                slots = [(b["bug_id"].split("_")[-1], b["buggy_solution"], b) for b in p["bugs"]]
            for slot_id, code, bug in slots:
                for lang in ("en", "es"):
                    block = sc["languages"][lang]
                    turns = [{"turn": ut["turn"], "role": "user",
                              "content": ut["template"].replace("{{buggy_solution}}", code)}
                             for ut in block["user_turns"]]
                    strategies = [ut["strategy"] for ut in block["user_turns"] if "strategy" in ut]
                    if bug is not None:
                        gt = {"bug_present": True, "bug_id": bug["bug_id"], "bug_category": bug["category"],
                              "bug_level": bug["level"], "bug_description": bug["edit_summary"]}
                        bug_ref, judge = bug["bug_id"], "test_execution+vcr"
                    else:
                        gt = {"bug_present": False, "bug_id": None, "bug_category": None,
                              "bug_level": None, "bug_description": "canonical solution (no injected bug)"}
                        bug_ref, judge = "canonical", "false_positive_check"
                    item = {
                        "item_id": f"{p['problem_id']}__{slot_id}__{sc['scenario_id']}__{lang}",
                        "schema_version": SCHEMA_VERSION,
                        "problem_ref": p["problem_id"], "bug_ref": bug_ref,
                        "scenario_ref": sc["scenario_id"], "scenario_family": sc["scenario_family"],
                        "language": lang, "original_id": p["original_id"], "source": p["source"],
                        "harness_kind": p["harness"]["kind"],
                        "rendered_prompts": {"system": block["system_prompt"], "turns": turns},
                        "ground_truth": gt,
                        "evaluation_config": {
                            "interaction_type": sc["interaction_type"], "max_turns": sc["max_turns"],
                            "pressure_escalation": strategies or None, "judge_strategy": judge,
                        },
                    }
                    item["content_hash"] = _hash(item)
                    items.append(item)
    return problems, scenarios, items

def main():
    problems, scenarios, items = build()
    n_buggy = sum(1 for s in scenarios if s.get("code_condition", "buggy") == "buggy")
    n_canon = sum(1 for s in scenarios if s.get("code_condition", "buggy") == "canonical")
    expected = len(problems) * 2 * (3 * n_buggy + 1 * n_canon)
    assert len(items) == expected, f"expected {expected} items, got {len(items)}"
    assert len({i['item_id'] for i in items}) == len(items), "duplicate item_id"
    try:
        import jsonschema
        schema = json.load(open(SCHEMA))
        for i in items:
            jsonschema.validate(i, schema)
        valid = "schema-validated (all %d)" % len(items)
    except ImportError:
        valid = "jsonschema absent; structural only"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for i in items:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")
    n_clean = sum(1 for i in items if not i["ground_truth"]["bug_present"])
    print(f"Wrote {len(items)} items -> {os.path.relpath(OUT)}  [{valid}]")
    print(f"  {n_buggy} buggy scenarios × 3 bugs + {n_canon} clean control × canonical, over {len(problems)} problems × 2 langs")
    print(f"  buggy items: {len(items) - n_clean} | clean-control items: {n_clean}")

if __name__ == "__main__":
    main()
