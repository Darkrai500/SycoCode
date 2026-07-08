"""Sandboxed harness executor — runs ONE grading task in an isolated subprocess.

Invoked as ``python -m eval._exec_worker`` with a JSON task on stdin; prints a
JSON result on stdout. Running model-generated code in a separate, timeout-bounded
process keeps Pass 2 deterministic and isolates crashes/hangs/`exit()` from the
parent. This is the standard EvalPlus/MBPP approach (subprocess + wall-clock cap),
not a hardened sandbox — adequate for grading reviews of benign benchmark functions.

Task: {kind, candidate, entry_point, test|reference,inputs,atol|imports,asserts}
Result: {tests_pass, n_total, n_failed, first_failing, error}
"""
from __future__ import annotations

import contextlib
import io
import json
import sys


def _safe(v):
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return repr(v)[:200]


def _equal(out, exp, atol):
    if out == exp:
        return True
    if atol and atol > 0:
        try:
            import numpy as np
            return bool(np.allclose(out, exp, rtol=1e-7, atol=atol))
        except Exception:
            return False
    # float tolerance even at atol==0 (mirrors EvalPlus is_floats default 1e-6)
    try:
        if isinstance(out, float) or isinstance(exp, float):
            return abs(out - exp) <= 1e-6
    except (TypeError, ValueError):
        pass
    return False


def _define(code, ns):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        exec(code, ns)


def run(task: dict) -> dict:
    kind = task["kind"]
    ep = task["entry_point"]
    ns: dict = {}
    try:
        _define(task["candidate"], ns)
    except Exception as e:  # noqa: BLE001
        return {"tests_pass": False, "n_total": None, "n_failed": None,
                "first_failing": None, "error": f"candidate_exec_error: {type(e).__name__}: {e}"[:240]}
    fn = ns.get(ep)
    if not callable(fn):
        return {"tests_pass": False, "n_total": None, "n_failed": None,
                "first_failing": None, "error": f"entry_point '{ep}' not defined by candidate"}

    if kind == "evalplus_check":
        try:
            _define(task["test"], ns)               # defines check()/assertion()/is_floats()
            check = ns.get("check")
            if not callable(check):
                return {"tests_pass": False, "n_total": None, "n_failed": None,
                        "first_failing": None, "error": "harness 'check' not defined"}
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                check(fn)
            return {"tests_pass": True, "n_total": None, "n_failed": 0, "first_failing": None, "error": None}
        except AssertionError as e:
            return {"tests_pass": False, "n_total": None, "n_failed": None,
                    "first_failing": str(e)[:200] or "assertion failed", "error": None}
        except Exception as e:  # noqa: BLE001
            return {"tests_pass": False, "n_total": None, "n_failed": None,
                    "first_failing": None, "error": f"{type(e).__name__}: {e}"[:240]}

    if kind == "mbpp_plus_differential":
        refns: dict = {}
        try:
            _define(task["reference"], refns)
        except Exception as e:  # noqa: BLE001
            return {"tests_pass": False, "n_total": None, "n_failed": None,
                    "first_failing": None, "error": f"reference_exec_error: {e}"[:200]}
        ref = refns.get(ep)
        atol = task.get("atol", 0)
        inputs = task["inputs"]
        nfail = 0
        first = None
        SENT = object()
        for inp in inputs:
            try:
                exp = ref(*inp)
            except Exception as e:  # noqa: BLE001
                exp = ("__exc__", type(e).__name__)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    out = fn(*inp)
            except Exception as e:  # noqa: BLE001
                out = ("__exc__", type(e).__name__)
            ok = (out == exp) if isinstance(exp, tuple) and exp and exp[0] == "__exc__" else _equal(out, exp, atol)
            if not ok:
                nfail += 1
                if first is None:
                    first = {"input": _safe(inp), "expected": _safe(exp), "got": _safe(out)}
        return {"tests_pass": nfail == 0, "n_total": len(inputs), "n_failed": nfail,
                "first_failing": first, "error": None}

    if kind == "assert_list":
        try:
            _define("\n".join(task.get("imports", [])), ns)
        except Exception:  # noqa: BLE001
            pass
        asserts = task["asserts"]
        nfail = 0
        first = None
        for a in asserts:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(a, ns)
            except Exception as e:  # noqa: BLE001
                nfail += 1
                if first is None:
                    first = {"assert": a, "error": f"{type(e).__name__}: {e}"[:160]}
        return {"tests_pass": nfail == 0, "n_total": len(asserts), "n_failed": nfail,
                "first_failing": first, "error": None}

    return {"tests_pass": False, "n_total": None, "n_failed": None,
            "first_failing": None, "error": f"unknown harness kind: {kind}"}


def main():
    try:
        task = json.load(sys.stdin)
        result = run(task)
    except Exception as e:  # noqa: BLE001
        result = {"tests_pass": False, "n_total": None, "n_failed": None,
                  "first_failing": None, "error": f"worker_error: {type(e).__name__}: {e}"[:240]}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
