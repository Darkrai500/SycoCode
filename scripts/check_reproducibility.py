#!/usr/bin/env python3
"""Run public offline checks in a disposable copy and save an auditable report.

Requires the CPython 3.12 requirements-reproducibility.lock environment.
No API keys, downloads, model calls or archived generated-code execution.
The existing oracle self-test executes two fixed benchmark fixtures locally.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

REQUIRED_TESTS = {"offline_selftest.py", "test_registry.py", "test_validate.py",
                  "test_vcr_harness.py", "test_vcr_panel.py", "test_verbal.py",
                  "test_reproducibility.py"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_files(root):
    paths = set()
    for pattern in ("eval/*.py", "tests/*.py", "scripts/*.py", "schema/*.json",
                    "data/problems/*.json*", "data/runs/aggregates/*.json", "config/*.json"):
        paths.update(p.relative_to(root).as_posix() for p in root.glob(pattern))
    paths.update({"requirements-reproducibility.lock", "requirements-replay.lock", "LICENSE.txt",
                  "docs/reproducibility/BUNDLE_README.md", "docs/reproducibility/import_provenance.json"})
    paths.update("tests/" + name for name in REQUIRED_TESTS)
    paths.update("data/replay/" + n for n in
                 ("item_ledger.jsonl.gz", "turn_ledger.jsonl.gz", "statistics.json"))
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True, help="new directory outside the source checkout")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    if out.exists() or args.out.is_symlink() or out.is_relative_to(root):
        parser.error("output must be a new directory outside the source checkout")
    out.mkdir(parents=True)
    report = {"schema_version": 1, "python": platform.python_version(), "platform": platform.platform(),
              "machine": platform.machine(), "steps": [], "status": "failed",
              "scope": "installation, offline regression checks, dataset schemas and aggregate figures"}
    try:
        if sys.version_info[:2] != (3, 12):
            raise ValueError("this validation profile requires CPython 3.12")
        lock = (root / "requirements-reproducibility.lock").read_text()
        pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s]+)", lock, re.M))
        if not pins:
            raise ValueError("empty dependency lock")
        versions = {name: importlib.metadata.version(name) for name in pins}
        report["dependencies"] = versions
        if versions != pins:
            raise ValueError("installed package versions differ from requirements-reproducibility.lock")
        files = selected_files(root)
        for name in files:
            path = root / name
            if not path.is_file() or path.is_symlink() or path.absolute() != path.resolve():
                raise ValueError("missing or redirected input: " + name)
        before = {name: digest(root / name) for name in files}
        report["source_sha256"] = before
        with tempfile.TemporaryDirectory(prefix="sycocode-check-") as temp:
            work = Path(temp).resolve()
            for name in files:
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / name, target)
            (work / "tmp").mkdir()
            env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT") if k in os.environ}
            env.update(TMPDIR=str(work / "tmp"), MPLCONFIGDIR=str(work / "mplconfig"),
                       PYTHONDONTWRITEBYTECODE="1")

            def run(name, script=None, arguments=()):
                command = [sys.executable, "-B", "-I", str(work / "scripts/offline_guard.py")]
                command += [str(work / script), *arguments] if script else ["--probe"]
                start = time.monotonic()
                try:
                    proc = subprocess.run(command, cwd=work, env=env, text=True,
                                          capture_output=True, timeout=300)
                    output, code = proc.stdout + proc.stderr, proc.returncode
                except subprocess.TimeoutExpired:
                    output, code = "check exceeded the 300-second timeout\n", 124
                output = output.replace(str(work), "<scratch>").replace(str(root), "<source>")
                (out / (name + ".log")).write_text(output)
                match = re.search(r"(\d+) passed, (\d+) failed", output)
                unittest = re.search(r"Ran (\d+) tests?", output)
                expected_attempts = 2 if script is None else 0
                guarded = f"SYCO_NETWORK_ATTEMPTS={expected_attempts}" in output
                step = {"name": name, "exit_code": code, "network_guard_checked": guarded,
                        "seconds": round(time.monotonic() - start, 3),
                        "passed": code == 0 and guarded}
                if match:
                    step.update(checks_passed=int(match[1]), checks_failed=int(match[2]))
                    step["passed"] &= int(match[2]) == 0
                elif unittest:
                    step["tests_run"] = int(unittest[1])
                report["steps"].append(step)
                print(f"{name}: {'PASS' if step['passed'] else 'FAIL'}", flush=True)

            run("network_guard_probe")
            for script in sorted((work / "tests").glob("*.py")):
                run(script.stem, script.relative_to(work).as_posix())
            run("revision_analysis", "scripts/test_revision_analysis.py")
            for layer in ("scenarios", "items"):
                run("build_" + layer, "scripts/build_" + layer + ".py")
                path = "data/problems/" + layer + ".jsonl"
                report.setdefault("dataset_rebuild", {})[layer] = {
                    "sha256": digest(work / path), "byte_identical": digest(work / path) == before[path]}
            import jsonschema
            schema_counts = {}
            for layer in ("problems", "scenarios", "items"):
                schema = json.loads((work / "schema" / (layer + ".schema.json")).read_text())
                cls = jsonschema.validators.validator_for(schema)
                cls.check_schema(schema)
                validator = cls(schema)
                rows = [json.loads(line) for line in (work / "data/problems" / (layer + ".jsonl")).read_text().splitlines()]
                for row in rows:
                    validator.validate(row)
                schema_counts[layer] = len(rows)
            report["schema_validated"] = schema_counts
            if schema_counts != {"problems": 50, "scenarios": 7, "items": 1900}:
                raise ValueError("unexpected dataset coverage")
            run("aggregate_figures", "scripts/tfg_make_figures.py")
            from PIL import Image
            figures = sorted((work / "docs/figures").glob("*.png"))
            for path in figures:
                with Image.open(path) as picture:
                    picture.verify()
            report["figures"] = {"pngs_decoded": len(figures), "expected": 20,
                                 "scope": "rendered from public aggregates; no claim of pixel equality"}
        report["inputs_unchanged"] = before == {name: digest(root / name) for name in files}
        passed = (all(s["passed"] for s in report["steps"]) and report["inputs_unchanged"]
                  and all(x["byte_identical"] for x in report["dataset_rebuild"].values())
                  and report["figures"]["pngs_decoded"] == 20)
        report["status"] = "passed" if passed else "failed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    (out / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("Report:", out / "validation.json")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
