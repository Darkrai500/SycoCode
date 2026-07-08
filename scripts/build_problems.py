#!/usr/bin/env python3
"""
build_problems.py — assemble Layer-1 problems.jsonl from data/problems/bug_specs.json.

For each problem: load the Layer-1 canonical (verify_bugs.layer1_canonical), apply
each bug's edits, derive a unified diff, RUN the oracle to capture failure evidence,
and emit a schema-conformant record. A record is written only if all three bugs are
verified_failing by execution (the generator re-verifies; it never trusts claims).

Run from repo root:  PYTHONPATH=scripts python3 scripts/build_problems.py
"""
import json, os, re, difflib
import verify_bugs as V

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "data", "problems", "problems.jsonl")
SCHEMA = os.path.join(HERE, "..", "schema", "problems.schema.json")
BUG_SPECS = os.path.join(HERE, "..", "data", "problems", "bug_specs.json")
CANDS = {c["candidate_id"]: c for c in
         (json.loads(l) for l in open(os.path.join(HERE, "..", "data", "problems", "candidates_phase3.jsonl")) if l.strip())}

def _ep_from_code(src):
    m = re.search(r"^\s*def\s+(\w+)\s*\(", src, re.M)
    return m.group(1) if m else None

def make_record(spec):
    cid = spec["id"]; c = CANDS[cid]; oid = c["original_id"]
    canon, source, canon_src, harness = V.layer1_canonical(oid)
    ep = V.canonical_full(oid)["entry_point"] or V.MBPPPLUS.get(oid, {}).get("entry_point") or _ep_from_code(canon)
    bugs = []
    for j, b in enumerate(spec["bugs"], start=1):
        edits = [tuple(e) for e in b["edits"]]
        buggy = V.apply_edits(canon, edits)
        res = V.run_suite(oid, buggy)
        if res["passes"] is not False:
            raise SystemExit(f"REFUSING {cid}_b{j} ({b['category']}): not verified_failing -> {res}")
        diff = "".join(difflib.unified_diff(canon.splitlines(True), buggy.splitlines(True),
                                            fromfile="canonical", tofile=f"{cid}_b{j}", n=2))
        ev = {"harness": harness["kind"], "detail": res["detail"]}
        m = re.search(r"in=(.+?) ref=", res["detail"])
        if m:
            ev["first_failing_input"] = m.group(1)
        bugs.append({"bug_id": f"{cid}_b{j}", "category": b["category"], "level": b["level"],
                     "edit_summary": b["summary"], "buggy_solution": buggy, "diff_unified": diff,
                     "verified_failing": True, "failure_evidence": ev})
    return {"problem_id": cid, "source": source, "original_id": oid, "entry_point": ep,
            "language": "python", "task_brief": c.get("task_brief", ""),
            "canonical_solution": canon, "harness": harness, "bugs": bugs,
            "provenance": {"admitted_categories": c.get("admitted_categories", []),
                           "categories_used": [b["category"] for b in spec["bugs"]],
                           "canonical_source": canon_src,
                           "category_notes": spec.get("category_notes", ""),
                           "level_notes": spec.get("level_notes", "")}}

def main():
    spec_list = json.load(open(BUG_SPECS))
    recs = [make_record(s) for s in spec_list]
    try:
        import jsonschema
        schema = json.load(open(SCHEMA))
        for r in recs:
            jsonschema.validate(r, schema)
        valid = "schema-validated"
    except ImportError:
        valid = "jsonschema absent; structural only"
    recs.sort(key=lambda r: r["problem_id"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    hist = Counter(b["level"] for r in recs for b in r["bugs"])
    cathist = Counter((b["category"], b["level"]) for r in recs for b in r["bugs"])
    print(f"Wrote {len(recs)} records ({sum(len(r['bugs']) for r in recs)} bugs) -> {os.path.relpath(OUT)}  [{valid}]")
    print("level histogram:", dict(hist))
    return recs, cathist

if __name__ == "__main__":
    main()
