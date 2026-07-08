#!/usr/bin/env python3
"""
verify_bugs.py — Layer-1 bug-injection verification harness for SycoCode.

Given a problem's original_id and a buggy full-function source, this reconstructs
the canonical test suite from data/raw/ (read-only) and runs it, returning:
  - syntactic validity (filter a),
  - whether >=1 test fails (filter b),
  - the first failing case (auditable ground truth),
  - timeout / crash signalling.

Two harness families:
  - evalplus_check : HumanEval / HumanEval+  (monolithic check(candidate))
  - assert_list    : MBPP-sanitized          (list of bare asserts + imports)

This module is import-safe; the __main__ block runs the CP2 pilot candidate set.
"""
import json, subprocess, tempfile, os, ast, textwrap, sys, re

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

def _load(path):
    return [json.loads(l) for l in open(path) if l.strip()]

HEP = {r["task_id"]: r for r in _load(os.path.join(RAW, "humanevalplus", "humanevalplus.jsonl"))}
MBPP = {("Mbpp/%d" % r["task_id"]): r for r in _load(os.path.join(RAW, "mbpp_sanitized", "mbpp_sanitized.jsonl"))}
_MPP_PATH = os.path.join(RAW, "mbppplus", "mbppplus.jsonl")
# EvalPlus MBPP+ (strong oracle): ~100+ inputs/problem. task_id == "Mbpp/<id>".
MBPPPLUS = {r["task_id"]: r for r in _load(_MPP_PATH)} if os.path.exists(_MPP_PATH) else {}

def canonical_full(oid):
    """Return the full self-contained canonical function text + harness metadata."""
    if oid.startswith("HumanEval/"):
        r = HEP[oid]
        return {
            "harness": "evalplus_check",
            "entry_point": r["entry_point"],
            "correct": r["prompt"] + r["canonical_solution"],
            "test": r["test"],
            "imports": [], "asserts": [],
        }
    elif oid.startswith("Mbpp/"):
        r = MBPP[oid]
        return {
            "harness": "assert_list",
            "entry_point": None,
            "correct": r["code"],
            "test": None,
            "imports": list(r.get("test_imports", [])),
            "asserts": list(r["test_list"]),
        }
    raise ValueError(oid)

def _run(src, timeout=15):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src); path = f.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT"
    finally:
        os.unlink(path)

# ---------------------------------------------------------------------------
# MBPP+ differential oracle.  Runs the reference (EvalPlus ground-truth canon)
# and the candidate over base_input+plus_input (~100+ cases) and compares
# outputs (atol for floats).  A divergence on >=1 input == admissible bug.
# Per-input SIGALRM guard turns a candidate hang into a recorded divergence.
# ---------------------------------------------------------------------------
_DIFF_TEMPLATE = '''
import json, signal, time
INPUTS = json.loads(__INPUTS_JSON__)
ATOL = __ATOL__
EP = __EP__
REF_SRC = __REF__
CAND_SRC = __CAND__

ref_ns = {}
cand_ns = {}
_ok = True
try:
    exec(REF_SRC, ref_ns)
except Exception as ex:
    print(json.dumps({"error": "ref_exec:%s" % type(ex).__name__})); _ok = False
try:
    exec(CAND_SRC, cand_ns)
except Exception as ex:
    print(json.dumps({"error": "cand_exec:%s" % type(ex).__name__})); _ok = False

if _ok:
    ref = ref_ns[EP]; cand = cand_ns[EP]
    class TO(Exception): pass
    def _h(s, f): raise TO()
    signal.signal(signal.SIGALRM, _h)
    def call(fn, args):
        signal.setitimer(signal.ITIMER_REAL, 1.0)
        try: return ("OK", fn(*args))
        except TO: return ("HANG", None)
        except Exception as ex: return ("EXC", type(ex).__name__)
        finally: signal.setitimer(signal.ITIMER_REAL, 0)
    def approx(a, b):
        if isinstance(a, bool) or isinstance(b, bool): return a == b
        if isinstance(a, float) or isinstance(b, float):
            try: return abs(a - b) <= ATOL
            except Exception: return a == b
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(approx(x, y) for x, y in zip(a, b))
        if isinstance(a, dict) and isinstance(b, dict):
            return list(a.keys()) == list(b.keys()) and all(approx(a[k], b[k]) for k in a)
        return a == b
    nfail = 0; first = None; seen = 0; trunc = False; t0 = time.time()
    for i, inp in enumerate(INPUTS):
        if time.time() - t0 > 35:
            trunc = True; break
        seen += 1
        e = call(ref, inp); g = call(cand, inp)
        if e[0] == "OK" and g[0] == "OK":
            same = approx(e[1], g[1])
        else:
            same = (e[0] != "OK" and g[0] != "OK")
        if not same:
            nfail += 1
            if first is None:
                first = {"i": i, "input": inp, "ref": [e[0], repr(e[1])[:50]], "cand": [g[0], repr(g[1])[:50]]}
    print(json.dumps({"nfail": nfail, "total": len(INPUTS), "seen": seen, "trunc": trunc, "first": first}))
'''

def _run_differential(oid, cand_src, ref_src=None):
    """Differential test cand_src vs the MBPP+ canonical over all MBPP+ inputs."""
    r = MBPPPLUS[oid]
    inputs = list(r["base_input"]) + list(r["plus_input"])
    script = (_DIFF_TEMPLATE
              .replace("__INPUTS_JSON__", json.dumps(json.dumps(inputs)))
              .replace("__ATOL__", repr(r.get("atol", 0)))
              .replace("__EP__", json.dumps(r["entry_point"]))
              .replace("__REF__", json.dumps(ref_src if ref_src is not None else r["canonical_solution"]))
              .replace("__CAND__", json.dumps(cand_src)))
    rc, out, err = _run(script, timeout=60)
    if rc == 124:
        return {"ok_syntax": True, "passes": None, "detail": "TIMEOUT(batch)"}
    try:
        data = json.loads((out.strip().splitlines() or ["{}"])[-1])
    except Exception:
        return {"ok_syntax": True, "passes": None, "detail": "parse-fail: " + (err.strip()[-140:] or out.strip()[-140:])}
    if "error" in data:
        return {"ok_syntax": True, "passes": None, "detail": data["error"]}
    if data.get("nfail", 0) == 0:
        if data.get("trunc"):
            return {"ok_syntax": True, "passes": None, "detail": "incomplete: budget hit after %d inputs, 0 divergences so far" % data.get("seen", 0)}
        return {"ok_syntax": True, "passes": True, "detail": "matches canonical on %d inputs" % data["total"]}
    f = data["first"]
    hang = " (incl. hangs; truncated)" if data.get("trunc") else ""
    return {"ok_syntax": True, "passes": False,
            "detail": "diverge %d/%d%s; first@%d in=%s ref=%s cand=%s" % (
                data["nfail"], data["total"], hang, f["i"], repr(f["input"])[:44], f["ref"], f["cand"])}

def integrity_check(oid):
    """Confirm OUR sanitized canonical agrees with the MBPP+ ground truth on all inputs."""
    if oid not in MBPPPLUS:
        return {"covered": False, "agrees": None, "detail": "not in MBPP+"}
    our = canonical_full(oid)["correct"]
    res = _run_differential(oid, our, ref_src=MBPPPLUS[oid]["canonical_solution"])
    return {"covered": True, "agrees": res["passes"], "detail": res["detail"]}

def run_suite(oid, full_src):
    """Run the canonical suite against `full_src`. Returns dict with pass/fail + detail."""
    # filter (a): syntactic validity
    try:
        ast.parse(full_src)
    except SyntaxError as e:
        return {"ok_syntax": False, "passes": None, "detail": f"SyntaxError: {e}"}
    # MBPP problems covered by MBPP+ go through the strong differential oracle.
    if oid.startswith("Mbpp/") and oid in MBPPPLUS:
        return _run_differential(oid, full_src)
    meta = canonical_full(oid)
    if meta["harness"] == "evalplus_check":
        ep = meta["entry_point"]
        # capture first failing case by wrapping check
        mod = full_src + "\n" + meta["test"] + textwrap.dedent(f"""
        try:
            check({ep})
            print("ALL_PASS")
        except AssertionError as e:
            print("FAIL_CHECK")
        except Exception as e:
            print("ERR:%s:%s" % (type(e).__name__, e))
        """)
        rc, out, err = _run(mod)
        if rc == 124:
            return {"ok_syntax": True, "passes": None, "detail": "TIMEOUT"}
        if "ALL_PASS" in out:
            return {"ok_syntax": True, "passes": True, "detail": "canonical-suite passes"}
        last = (out.strip().splitlines() or ["?"])[-1]
        return {"ok_syntax": True, "passes": False, "detail": last + (" | " + err.strip().splitlines()[-1] if err.strip() else "")}
    else:  # assert_list
        body = "\n".join(meta["imports"]) + "\n" + full_src + "\n"
        for i, a in enumerate(meta["asserts"]):
            body += f"try:\n{textwrap.indent(a, '    ')}\nexcept AssertionError:\n    print('FAIL_ASSERT_{i}')\nexcept Exception as _e:\n    print('ERR_ASSERT_{i}:%s'%type(_e).__name__)\n"
        body += "print('DONE')\n"
        rc, out, err = _run(body)
        if rc == 124:
            return {"ok_syntax": True, "passes": None, "detail": "TIMEOUT"}
        fails = [ln for ln in out.splitlines() if ln.startswith(("FAIL_ASSERT_", "ERR_ASSERT_"))]
        if not fails and "DONE" in out:
            return {"ok_syntax": True, "passes": True, "detail": "all asserts pass"}
        return {"ok_syntax": True, "passes": False, "detail": ",".join(fails) or ("crash: " + (err.strip().splitlines()[-1] if err.strip() else "?"))}

def apply_edits(correct, edits):
    """edits = list of (old, new). Each must match exactly once. Returns buggy src."""
    src = correct
    for old, new in edits:
        n = src.count(old)
        if n != 1:
            raise ValueError(f"edit anchor matched {n} times (need 1): {old!r}")
        src = src.replace(old, new)
    return src


def layer1_canonical(oid):
    """Resolve the Layer-1 canonical + harness for a problem.

    Returns (canonical_solution, source, canonical_source, harness_dict).
    MBPP covered by MBPP+ -> EvalPlus ground-truth canonical + differential oracle;
    uncovered MBPP -> sanitized assert list; HumanEval/+ -> prompt+canonical + check.
    """
    if oid.startswith("HumanEval/"):
        m = canonical_full(oid)
        return m["correct"], "humanevalplus", "humanevalplus", {"kind": "evalplus_check", "test": m["test"]}
    if oid in MBPPPLUS:
        r = MBPPPLUS[oid]
        canon = r["canonical_solution"]
        return canon, "mbppplus", "mbppplus_ground_truth", {
            "kind": "mbpp_plus_differential", "reference": canon,
            "inputs": list(r["base_input"]) + list(r["plus_input"]), "atol": r.get("atol", 0)}
    m = canonical_full(oid)
    return m["correct"], "mbpp_sanitized", "mbpp_sanitized", {
        "kind": "assert_list", "imports": m["imports"], "asserts": m["asserts"]}


def _candidates():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "problems", "candidates_phase3.jsonl")
    return {c["candidate_id"]: c for c in _load(path)}


# ---------------------------------------------------------------------------
# CLI for bug-injection agents:
#   info  <cand_id>                 -> JSON: metadata + the exact canonical to edit
#   check <original_id> <edits>     -> JSON: verified_failing verdict + first failing case
#                                      edits = JSON list of [old, new] string pairs
# ---------------------------------------------------------------------------
def _cmd_info(cand_id):
    c = _candidates()[cand_id]
    oid = c["original_id"]
    canon, source, csrc, harness = layer1_canonical(oid)
    ep = canonical_full(oid)["entry_point"] or MBPPPLUS.get(oid, {}).get("entry_point")
    ncases = len(harness.get("inputs", harness.get("asserts", [])))
    return {
        "candidate_id": cand_id, "original_id": oid, "entry_point": ep,
        "admitted_categories": c.get("admitted_categories"),
        "task_brief": c.get("task_brief"), "rationale": c.get("rationale"),
        "source": source, "canonical_source": csrc, "harness_kind": harness["kind"],
        "n_oracle_cases": ncases, "canonical_to_edit": canon,
    }

def _cmd_check(oid, edits_json):
    edits = [tuple(e) for e in json.loads(edits_json)]
    canon, _s, _c, _h = layer1_canonical(oid)
    try:
        buggy = apply_edits(canon, edits)
    except ValueError as e:
        return {"error": str(e), "verified_failing": False}
    res = run_suite(oid, buggy)
    out = {"verified_failing": res["passes"] is False, "ok_syntax": res["ok_syntax"], "detail": res["detail"]}
    m = re.search(r"in=(.+?) ref=", res.get("detail") or "")
    if m:
        out["first_failing_input"] = m.group(1)
    return out

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="SycoCode Layer-1 bug verification CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("info"); pi.add_argument("cand_id")
    pc = sub.add_parser("check"); pc.add_argument("original_id")
    pc.add_argument("edits_json", help="JSON list of [old,new] pairs, or @path to a file holding that JSON")
    pcur = sub.add_parser("current"); pcur.add_argument("cand_id")
    a = ap.parse_args()
    if a.cmd == "info":
        print(json.dumps(_cmd_info(a.cand_id), ensure_ascii=False, indent=2))
    elif a.cmd == "current":
        ppath = os.path.join(os.path.dirname(__file__), "..", "data", "problems", "problems.jsonl")
        rec = next((r for r in _load(ppath) if r["problem_id"] == a.cand_id), None)
        if rec is None:
            print(json.dumps({"error": "not built yet"}))
        else:
            print(json.dumps({"problem_id": rec["problem_id"],
                "current_bugs": [{"category": b["category"], "level": b["level"], "summary": b["edit_summary"]} for b in rec["bugs"]]},
                ensure_ascii=False, indent=2))
    elif a.cmd == "check":
        ej = a.edits_json
        if ej.startswith("@"):
            ej = open(ej[1:]).read()
        print(json.dumps(_cmd_check(a.original_id, ej), ensure_ascii=False))
